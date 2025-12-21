package calendarapp.swing;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * HTTP-backed implementation of {@link CalendarBackend} that communicates with the backend server.
 * <p>
 * The server is expected to expose the following endpoints using JSON payloads:
 * <ul>
 *     <li>GET /events[?includeCanceled=true|false&calendarId=...&date=YYYY-MM-DD]</li>
 *     <li>PUT /events/{id}</li>
 *     <li>POST /events/{id}/cancel</li>
 *     <li>POST /events/{id}/reschedule</li>
 * </ul>
 * Responses return either an {@code {"events":[...]}} envelope or a single event object.
 */
public final class HttpCalendarBackend implements CalendarBackend {
    private final HttpClient client;
    private final URI baseUri;
    private final DateTimeFormatter formatter = DateTimeFormatter.ISO_OFFSET_DATE_TIME;

    public HttpCalendarBackend(String baseUrl) {
        this(HttpClient.newHttpClient(), baseUrl);
    }

    HttpCalendarBackend(HttpClient client, String baseUrl) {
        this.client = Objects.requireNonNull(client, "client");
        this.baseUri = URI.create(Objects.requireNonNull(baseUrl, "baseUrl"));
    }

    @Override
    public List<CalendarEvent> listEvents() {
        return filterCanceled(fetchEvents(false, null, null, false));
    }

    @Override
    public List<CalendarEvent> listEventsIncludingCanceled() {
        return fetchEvents(true, null, null, true);
    }

    @Override
    public List<CalendarEvent> listEventsForDate(LocalDate date) {
        return filterCanceled(fetchEvents(false, null, date, false));
    }

    @Override
    public List<CalendarEvent> listEventsForCalendar(String calendarId) {
        return filterCanceled(fetchEvents(false, calendarId, null, false));
    }

    @Override
    public List<CalendarEvent> listEventsForCalendarOnDate(String calendarId, LocalDate date) {
        return filterCanceled(fetchEvents(false, calendarId, date, false));
    }

    @Override
    public CalendarEvent upsertEvent(CalendarEvent event) {
        Objects.requireNonNull(event, "event");
        URI uri = buildUri("/events/" + urlEncode(event.getId()), Map.of());
        String json = serializeEvent(event);
        HttpRequest request = HttpRequest.newBuilder(uri)
                .header("Content-Type", "application/json")
                .PUT(HttpRequest.BodyPublishers.ofString(json))
                .build();
        return parseEvent(send(request));
    }

    @Override
    public CalendarEvent cancelEvent(String eventId) {
        Objects.requireNonNull(eventId, "eventId");
        return performEventAction(eventId, "cancel", null);
    }

    @Override
    public CalendarEvent rescheduleEvent(String eventId, ZonedDateTime start, ZonedDateTime end, String timezone) {
        Objects.requireNonNull(eventId, "eventId");
        Objects.requireNonNull(start, "start");
        Objects.requireNonNull(end, "end");
        Objects.requireNonNull(timezone, "timezone");
        Map<String, Object> payload = new HashMap<>();
        payload.put("start", formatter.format(start));
        payload.put("end", formatter.format(end));
        payload.put("timezone", timezone);
        return performEventAction(eventId, "reschedule", payload);
    }

    private CalendarEvent performEventAction(String eventId, String action, Map<String, Object> payload) {
        URI uri = buildUri("/events/" + urlEncode(eventId) + "/" + action, Map.of());
        HttpRequest.Builder builder = HttpRequest.newBuilder(uri)
                .header("Content-Type", "application/json")
                .POST(payload == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(serializeObject(payload)));
        return parseEvent(send(builder.build()));
    }

    private List<CalendarEvent> fetchEvents(boolean includeCanceled, String calendarId, LocalDate date, boolean preserveCanceled) {
        Map<String, String> params = new HashMap<>();
        params.put("includeCanceled", String.valueOf(includeCanceled));
        if (calendarId != null) {
            params.put("calendarId", calendarId);
        }
        if (date != null) {
            params.put("date", date.toString());
        }
        URI uri = buildUri("/events", params);
        String body = send(HttpRequest.newBuilder(uri).GET().build());
        Object parsed = SimpleJsonParser.parse(body);
        if (!(parsed instanceof Map)) {
            throw new IllegalStateException("Unexpected events payload");
        }
        Object eventsValue = ((Map<?, ?>) parsed).get("events");
        if (!(eventsValue instanceof List)) {
            throw new IllegalStateException("Missing events list in payload");
        }
        List<?> rawEvents = (List<?>) eventsValue;
        List<CalendarEvent> events = new ArrayList<>();
        for (Object raw : rawEvents) {
            if (!(raw instanceof Map)) {
                throw new IllegalStateException("Invalid event entry");
            }
            events.add(toEvent((Map<?, ?>) raw));
        }
        return preserveCanceled ? events : filterCanceled(events);
    }

    private CalendarEvent parseEvent(String body) {
        Object parsed = SimpleJsonParser.parse(body);
        if (!(parsed instanceof Map)) {
            throw new IllegalStateException("Unexpected event payload");
        }
        return toEvent((Map<?, ?>) parsed);
    }

    private CalendarEvent toEvent(Map<?, ?> data) {
        String id = getString(data, "id");
        String calendarId = getString(data, "calendar_id");
        String title = getString(data, "title");
        String timezone = getString(data, "timezone");
        ZoneId zone = ZoneId.of(timezone);
        ZonedDateTime start = ZonedDateTime.parse(getString(data, "start")).withZoneSameInstant(zone);
        ZonedDateTime end = ZonedDateTime.parse(getString(data, "end")).withZoneSameInstant(zone);
        String description = asNullableString(data.get("description"));
        boolean canceled = getBoolean(data, "canceled", false);
        return new CalendarEvent(id, calendarId, title, start, end, timezone, description, canceled);
    }

    private String getString(Map<?, ?> data, String key) {
        Object value = data.get(key);
        if (!(value instanceof String)) {
            throw new IllegalStateException("Missing string field: " + key);
        }
        return (String) value;
    }

    private boolean getBoolean(Map<?, ?> data, String key, boolean defaultValue) {
        Object value = data.get(key);
        if (value == null) {
            return defaultValue;
        }
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        throw new IllegalStateException("Invalid boolean field: " + key);
    }

    private String asNullableString(Object value) {
        return value == null ? null : value.toString();
    }

    private List<CalendarEvent> filterCanceled(List<CalendarEvent> events) {
        List<CalendarEvent> filtered = new ArrayList<>();
        for (CalendarEvent event : events) {
            if (!event.isCanceled()) {
                filtered.add(event);
            }
        }
        return filtered;
    }

    private String serializeEvent(CalendarEvent event) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("id", event.getId());
        payload.put("calendar_id", event.getCalendarId());
        payload.put("title", event.getTitle());
        payload.put("start", formatter.format(event.getStart()));
        payload.put("end", formatter.format(event.getEnd()));
        payload.put("timezone", event.getTimezone());
        payload.put("description", event.getDescription());
        payload.put("canceled", event.isCanceled());
        return serializeObject(payload);
    }

    private String serializeObject(Map<String, Object> payload) {
        StringBuilder builder = new StringBuilder();
        builder.append("{");
        boolean first = true;
        for (Map.Entry<String, Object> entry : payload.entrySet()) {
            if (!first) {
                builder.append(",");
            }
            first = false;
            builder.append("\"").append(escape(entry.getKey())).append("\":");
            Object value = entry.getValue();
            if (value == null) {
                builder.append("null");
            } else if (value instanceof Boolean || value instanceof Number) {
                builder.append(value.toString());
            } else {
                builder.append("\"").append(escape(value.toString())).append("\"");
            }
        }
        builder.append("}");
        return builder.toString();
    }

    private String escape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private URI buildUri(String path, Map<String, String> queryParams) {
        StringBuilder builder = new StringBuilder();
        URI resolved = baseUri.resolve(path);
        builder.append(resolved.toString());
        if (!queryParams.isEmpty()) {
            builder.append(path.contains("?") ? "&" : "?");
            boolean first = true;
            for (Map.Entry<String, String> entry : queryParams.entrySet()) {
                if (!first) {
                    builder.append("&");
                }
                first = false;
                builder.append(urlEncode(entry.getKey()))
                        .append("=")
                        .append(urlEncode(entry.getValue()));
            }
        }
        return URI.create(builder.toString());
    }

    private String urlEncode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private String send(HttpRequest request) {
        try {
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new IllegalStateException("Backend returned error " + response.statusCode());
            }
            return response.body();
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Failed to call backend", exc);
        } catch (IOException exc) {
            throw new IllegalStateException("Failed to call backend", exc);
        }
    }

    /**
     * Minimal JSON parser that supports objects, arrays, strings, booleans, null, and numbers.
     * This avoids extra dependencies while remaining sufficient for the backend responses.
     */
    static final class SimpleJsonParser {
        private final String json;
        private int index;

        private SimpleJsonParser(String json) {
            this.json = Objects.requireNonNull(json, "json");
        }

        static Object parse(String json) {
            SimpleJsonParser parser = new SimpleJsonParser(json);
            Object value = parser.parseValue();
            parser.skipWhitespace();
            if (parser.hasMore()) {
                throw new IllegalStateException("Unexpected trailing content");
            }
            return value;
        }

        private Object parseValue() {
            skipWhitespace();
            if (!hasMore()) {
                throw new IllegalStateException("Empty JSON content");
            }
            char ch = peek();
            if (ch == '{') {
                return parseObject();
            }
            if (ch == '[') {
                return parseArray();
            }
            if (ch == '"') {
                return parseString();
            }
            if (startsWith("true")) {
                index += 4;
                return Boolean.TRUE;
            }
            if (startsWith("false")) {
                index += 5;
                return Boolean.FALSE;
            }
            if (startsWith("null")) {
                index += 4;
                return null;
            }
            return parseNumber();
        }

        private Map<String, Object> parseObject() {
            expect('{');
            Map<String, Object> map = new HashMap<>();
            skipWhitespace();
            if (peek() == '}') {
                index++;
                return map;
            }
            while (true) {
                String key = parseString();
                skipWhitespace();
                expect(':');
                Object value = parseValue();
                map.put(key, value);
                skipWhitespace();
                char ch = peek();
                if (ch == '}') {
                    index++;
                    break;
                }
                expect(',');
            }
            return map;
        }

        private List<Object> parseArray() {
            expect('[');
            List<Object> list = new ArrayList<>();
            skipWhitespace();
            if (peek() == ']') {
                index++;
                return list;
            }
            while (true) {
                list.add(parseValue());
                skipWhitespace();
                char ch = peek();
                if (ch == ']') {
                    index++;
                    break;
                }
                expect(',');
            }
            return list;
        }

        private String parseString() {
            expect('"');
            StringBuilder builder = new StringBuilder();
            while (hasMore()) {
                char ch = next();
                if (ch == '"') {
                    return builder.toString();
                }
                if (ch == '\\') {
                    if (!hasMore()) {
                        throw new IllegalStateException("Invalid escape sequence");
                    }
                    char esc = next();
                    switch (esc) {
                        case '"':
                        case '\\':
                        case '/':
                            builder.append(esc);
                            break;
                        case 'b':
                            builder.append('\b');
                            break;
                        case 'f':
                            builder.append('\f');
                            break;
                        case 'n':
                            builder.append('\n');
                            break;
                        case 'r':
                            builder.append('\r');
                            break;
                        case 't':
                            builder.append('\t');
                            break;
                        default:
                            throw new IllegalStateException("Unsupported escape sequence: \\" + esc);
                    }
                } else {
                    builder.append(ch);
                }
            }
            throw new IllegalStateException("Unterminated string literal");
        }

        private Number parseNumber() {
            int start = index;
            while (hasMore()) {
                char ch = peek();
                if (Character.isDigit(ch) || ch == '-' || ch == '.' || ch == '+') {
                    index++;
                } else {
                    break;
                }
            }
            String slice = json.substring(start, index);
            try {
                if (slice.contains(".") || slice.contains("e") || slice.contains("E")) {
                    return Double.parseDouble(slice);
                }
                return Long.parseLong(slice);
            } catch (NumberFormatException exc) {
                throw new IllegalStateException("Invalid number: " + slice, exc);
            }
        }

        private void skipWhitespace() {
            while (hasMore() && Character.isWhitespace(peek())) {
                index++;
            }
        }

        private void expect(char expected) {
            skipWhitespace();
            if (!hasMore() || json.charAt(index) != expected) {
                throw new IllegalStateException("Expected '" + expected + "'");
            }
            index++;
        }

        private boolean startsWith(String expected) {
            return json.startsWith(expected, index);
        }

        private char peek() {
            return json.charAt(index);
        }

        private char next() {
            return json.charAt(index++);
        }

        private boolean hasMore() {
            return index < json.length();
        }
    }
}
