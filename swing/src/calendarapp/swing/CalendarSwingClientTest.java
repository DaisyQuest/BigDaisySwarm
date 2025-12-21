package calendarapp.swing;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;

/**
 * Lightweight test harness that exercises the Swing client and backend without external tooling.
 */
public final class CalendarSwingClientTest {
    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        testBackendFiltersAndSorts();
        testBackendCalendarFilteringAndCancelation();
        testHttpBackendFetchesAndFiltersEvents();
        testHttpBackendHandlesErrors();
        testClientPopulatesTable();
        testClientShowsCanceledFlag();
        testClientClearsTableOnEmptyFilter();
        testRejectsInvalidEventDurations();
        testTableIsReadOnly();
        System.out.println("Swing client tests passed");
    }

    private static void testBackendFiltersAndSorts() {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        List<CalendarEvent> all = backend.listEvents();
        if (all.size() != 3) {
            throw new AssertionError("Expected 3 active events, got " + all.size());
        }
        if (!all.get(0).getId().equals("kickoff") || !"Planning".equals(all.get(1).getTitle())) {
            throw new AssertionError("Events should be sorted by start time and exclude canceled entries");
        }
        List<CalendarEvent> planningDay = backend.listEventsForDate(LocalDate.of(2025, 1, 17));
        if (planningDay.size() != 1 || !planningDay.get(0).getId().equals("planning")) {
            throw new AssertionError("Expected planning event on Jan 17");
        }
        List<CalendarEvent> empty = backend.listEventsForDate(LocalDate.of(2030, 1, 1));
        if (!empty.isEmpty()) {
            throw new AssertionError("Unexpected events for empty date");
        }
        if (backend.listEventsForDate(null).size() != 3) {
            throw new AssertionError("Null date should return all events");
        }
    }

    private static void testBackendCalendarFilteringAndCancelation() {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        List<CalendarEvent> teamEvents = backend.listEventsForCalendar("team");
        if (teamEvents.size() != 3) {
            throw new AssertionError("Team calendar should only return active team events");
        }
        List<CalendarEvent> opsEvents = backend.listEventsForCalendar("ops");
        if (!opsEvents.isEmpty()) {
            throw new AssertionError("Canceled ops event should be filtered from default queries");
        }
        List<CalendarEvent> allIncludingCanceled = backend.listEventsIncludingCanceled();
        if (allIncludingCanceled.size() != 4) {
            throw new AssertionError("Expected canceled events to be present when requested");
        }
        CalendarEvent canceled = allIncludingCanceled.stream()
                .filter(CalendarEvent::isCanceled)
                .findFirst()
                .orElseThrow(() -> new AssertionError("Canceled event missing"));
        if (!"canceled".equals(canceled.getId())) {
            throw new AssertionError("Unexpected canceled event id: " + canceled.getId());
        }
        backend.rescheduleEvent("retro",
                allIncludingCanceled.get(0).getStart().minusDays(2),
                allIncludingCanceled.get(0).getEnd().minusDays(2),
                "UTC");
        List<CalendarEvent> reordered = backend.listEvents();
        if (!"retro".equals(reordered.get(0).getId())) {
            throw new AssertionError("Rescheduling should update sort order");
        }
        CalendarEvent canceledEvent = backend.cancelEvent("planning");
        if (!canceledEvent.isCanceled()) {
            throw new AssertionError("cancelEvent should mark event as canceled");
        }
        if (backend.listEvents().size() != 2) {
            throw new AssertionError("Canceled events should no longer appear in active list");
        }
    }

    private static void testHttpBackendFetchesAndFiltersEvents() throws Exception {
        String eventsPayload = "{\"events\":[{" +
                "\"id\":\"kickoff\",\"calendar_id\":\"team\",\"title\":\"Kickoff\",\"start\":\"2025-01-10T15:00:00Z\",\"end\":\"2025-01-10T16:00:00Z\",\"timezone\":\"UTC\",\"description\":\"Start\",\"canceled\":false}," +
                "{\"id\":\"obsolete\",\"calendar_id\":\"ops\",\"title\":\"Obsolete\",\"start\":\"2025-01-11T09:00:00Z\",\"end\":\"2025-01-11T10:00:00Z\",\"timezone\":\"UTC\",\"description\":\"Old\",\"canceled\":true}" +
                "]}";
        try (MockEventServer server = new MockEventServer(req -> new MockResponse(200, eventsPayload))) {
            HttpCalendarBackend backend = new HttpCalendarBackend(server.baseUri().toString());
            List<CalendarEvent> active = backend.listEvents();
            if (active.size() != 1 || !"kickoff".equals(active.get(0).getId())) {
                throw new AssertionError("listEvents should exclude canceled entries");
            }
            if (!server.lastQuery.contains("includeCanceled=false")) {
                throw new AssertionError("listEvents should request active events only");
            }

            List<CalendarEvent> all = backend.listEventsIncludingCanceled();
            if (all.size() != 2) {
                throw new AssertionError("listEventsIncludingCanceled should return all events");
            }
            if (!server.lastQuery.contains("includeCanceled=true")) {
                throw new AssertionError("includeCanceled flag missing");
            }

            List<CalendarEvent> team = backend.listEventsForCalendar("team");
            if (team.size() != 1 || !"team".equals(team.get(0).getCalendarId())) {
                throw new AssertionError("Filtering by calendar should work");
            }
            if (!server.lastQuery.contains("calendarId=team")) {
                throw new AssertionError("calendarId query parameter missing");
            }

            List<CalendarEvent> dated = backend.listEventsForCalendarOnDate("team", LocalDate.of(2025, 1, 10));
            if (dated.isEmpty()) {
                throw new AssertionError("Date filter should return the matching event");
            }
            if (!server.lastQuery.contains("date=2025-01-10")) {
                throw new AssertionError("Date query parameter missing");
            }

            ZonedDateTime newStart = ZonedDateTime.of(2025, 1, 10, 17, 0, 0, 0, ZoneId.of("UTC"));
            ZonedDateTime newEnd = newStart.plusHours(1);
            server.responder = req -> {
                if (!req.body().contains("Kickoff")) {
                    throw new AssertionError("Upsert should send event payload");
                }
                return new MockResponse(200, "{\"id\":\"kickoff\",\"calendar_id\":\"team\",\"title\":\"Kickoff\",\"start\":\"2025-01-10T15:00:00Z\",\"end\":\"2025-01-10T16:00:00Z\",\"timezone\":\"UTC\",\"description\":\"Start\",\"canceled\":false}");
            };
            CalendarEvent upserted = backend.upsertEvent(active.get(0));
            if (!"/events/kickoff".equals(server.lastPath) || !"PUT".equals(server.lastMethod)) {
                throw new AssertionError("Upsert should target /events/{id} with PUT");
            }
            if (!"kickoff".equals(upserted.getId())) {
                throw new AssertionError("Upsert response should be parsed");
            }

            server.responder = req -> {
                return new MockResponse(200, "{\"id\":\"kickoff\",\"calendar_id\":\"team\",\"title\":\"Kickoff\",\"start\":\"2025-01-10T17:00:00Z\",\"end\":\"2025-01-10T18:00:00Z\",\"timezone\":\"UTC\",\"description\":\"Start\",\"canceled\":false}");
            };
            CalendarEvent rescheduled = backend.rescheduleEvent("kickoff", newStart, newEnd, "UTC");
            if (!"/events/kickoff/reschedule".equals(server.lastPath) || !"POST".equals(server.lastMethod)) {
                throw new AssertionError("Reschedule should post to reschedule endpoint");
            }
            if (!rescheduled.getStart().equals(newStart)) {
                throw new AssertionError("Reschedule should parse returned start time");
            }

            server.responder = req -> {
                return new MockResponse(200, "{\"id\":\"kickoff\",\"calendar_id\":\"team\",\"title\":\"Kickoff\",\"start\":\"2025-01-10T17:00:00Z\",\"end\":\"2025-01-10T18:00:00Z\",\"timezone\":\"UTC\",\"description\":\"Start\",\"canceled\":true}");
            };
            CalendarEvent canceled = backend.cancelEvent("kickoff");
            if (!canceled.isCanceled()) {
                throw new AssertionError("Cancel should mark the event canceled");
            }
            if (!"/events/kickoff/cancel".equals(server.lastPath)) {
                throw new AssertionError("Cancel should hit cancel endpoint");
            }
        }
    }

    private static void testHttpBackendHandlesErrors() throws Exception {
        try (MockEventServer server = new MockEventServer(exchange -> new MockResponse(500, "{\"error\": \"boom\"}"))) {
            HttpCalendarBackend backend = new HttpCalendarBackend(server.baseUri().toString());
            boolean threw = false;
            try {
                backend.listEvents();
            } catch (IllegalStateException ex) {
                threw = true;
            }
            if (!threw) {
                throw new AssertionError("HTTP errors should raise exceptions");
            }
        }

        try (MockEventServer server = new MockEventServer(exchange -> new MockResponse(200, "not-json"))) {
            HttpCalendarBackend backend = new HttpCalendarBackend(server.baseUri().toString());
            boolean threw = false;
            try {
                backend.listEvents();
            } catch (IllegalStateException ex) {
                threw = true;
            }
            if (!threw) {
                throw new AssertionError("Invalid JSON should raise exceptions");
            }
        }
    }

    private static void testClientPopulatesTable() throws Exception {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        CalendarSwingClient client = new CalendarSwingClient(backend, false);
        SwingUtilities.invokeAndWait(client::loadAllEvents);
        DefaultTableModel model = client.getTableModel();
        if (model.getRowCount() != 3) {
            throw new AssertionError("Expected table to contain all events");
        }
        Object title = model.getValueAt(0, 0);
        if (!"team".equals(title)) {
            throw new AssertionError("First column should contain calendar id");
        }
        Object status = model.getValueAt(0, 6);
        if (!"Active".equals(status)) {
            throw new AssertionError("Active events should display active status");
        }
    }

    private static void testClientShowsCanceledFlag() throws Exception {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        CalendarSwingClient client = new CalendarSwingClient(backend, false);
        SwingUtilities.invokeAndWait(client::filterCanceledEvents);
        if (client.getTableModel().getRowCount() != 1) {
            throw new AssertionError("Only one canceled event should be shown");
        }
        Object status = client.getTableModel().getValueAt(0, 6);
        if (!"Canceled".equals(status)) {
            throw new AssertionError("Canceled events should be labeled");
        }
    }

    private static void testClientClearsTableOnEmptyFilter() throws Exception {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        CalendarSwingClient client = new CalendarSwingClient(backend, false);
        SwingUtilities.invokeAndWait(() -> client.filterByDate(LocalDate.of(2030, 1, 1)));
        if (client.getTableModel().getRowCount() != 0) {
            throw new AssertionError("Table should be empty for dates with no events");
        }
    }

    private static void testRejectsInvalidEventDurations() {
        boolean threw = false;
        try {
            new CalendarEvent(
                    "invalid",
                    "team",
                    "Broken",
                    InMemoryCalendarBackend.sampleData().listEventsIncludingCanceled().get(0).getEnd(),
                    InMemoryCalendarBackend.sampleData().listEventsIncludingCanceled().get(0).getStart(),
                    "UTC",
                    null,
                    false);
        } catch (IllegalArgumentException ex) {
            threw = true;
        }
        if (!threw) {
            throw new AssertionError("Expected invalid event duration to throw");
        }
    }

    private static void testTableIsReadOnly() throws Exception {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        CalendarSwingClient client = new CalendarSwingClient(backend, false);
        SwingUtilities.invokeAndWait(client::loadAllEvents);
        if (client.getTable().isCellEditable(0, 0)) {
            throw new AssertionError("Table cells should be read-only");
        }
    }

    private record MockResponse(int status, String body) {}

    private record MockRequest(String path, String query, String method, String body) {}

    private static final class MockEventServer implements AutoCloseable {
        private final HttpServer server;
        private final java.util.concurrent.ExecutorService executorService = Executors.newSingleThreadExecutor();
        volatile Function<MockRequest, MockResponse> responder;
        volatile String lastPath = "";
        volatile String lastQuery = "";
        volatile String lastMethod = "";
        volatile String lastBody = "";

        MockEventServer(Function<MockRequest, MockResponse> handler) throws IOException {
            this.server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
            this.responder = handler;
            this.server.createContext("/", this::handle);
            this.server.setExecutor(executorService);
            this.server.start();
        }

        URI baseUri() {
            return URI.create("http://localhost:" + server.getAddress().getPort());
        }

        @Override
        public void close() {
            server.stop(0);
            executorService.shutdownNow();
            try {
                executorService.awaitTermination(1, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }

        private void handle(HttpExchange exchange) throws IOException {
            String path = exchange.getRequestURI().getPath();
            String query = exchange.getRequestURI().getQuery() == null ? "" : exchange.getRequestURI().getQuery();
            String method = exchange.getRequestMethod();
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            this.lastPath = path;
            this.lastQuery = query;
            this.lastMethod = method;
            this.lastBody = body;

            MockRequest request = new MockRequest(path, query, method, body);
            Function<MockRequest, MockResponse> handler = responder;
            MockResponse response = handler == null ? new MockResponse(404, "{}") : handler.apply(request);
            respond(exchange, response);
        }

        static void respond(HttpExchange exchange, MockResponse response) throws IOException {
            byte[] body = response.body().getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(response.status(), body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        }
    }
}
