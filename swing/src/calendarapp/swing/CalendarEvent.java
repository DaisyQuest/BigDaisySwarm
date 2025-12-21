package calendarapp.swing;

import java.time.ZonedDateTime;
import java.util.Objects;

/** Immutable event model used by the Swing client. */
public final class CalendarEvent {
    private final String id;
    private final String title;
    private final ZonedDateTime start;
    private final ZonedDateTime end;
    private final String timezone;

    public CalendarEvent(String id, String title, ZonedDateTime start, ZonedDateTime end, String timezone) {
        this.id = Objects.requireNonNull(id, "id");
        this.title = Objects.requireNonNull(title, "title");
        this.start = Objects.requireNonNull(start, "start");
        this.end = Objects.requireNonNull(end, "end");
        this.timezone = Objects.requireNonNull(timezone, "timezone");
        if (!start.isBefore(end)) {
            throw new IllegalArgumentException("start must be before end");
        }
    }

    public String getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public ZonedDateTime getStart() {
        return start;
    }

    public ZonedDateTime getEnd() {
        return end;
    }

    public String getTimezone() {
        return timezone;
    }
}
