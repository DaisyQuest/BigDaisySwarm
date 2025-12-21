package calendarapp.swing;

import java.time.ZonedDateTime;
import java.util.Objects;

/** Immutable event model used by the Swing client. */
public final class CalendarEvent {
    private final String id;
    private final String calendarId;
    private final String title;
    private final ZonedDateTime start;
    private final ZonedDateTime end;
    private final String timezone;
    private final String description;
    private final boolean canceled;

    public CalendarEvent(
            String id,
            String calendarId,
            String title,
            ZonedDateTime start,
            ZonedDateTime end,
            String timezone) {
        this(id, calendarId, title, start, end, timezone, null, false);
    }

    public CalendarEvent(
            String id,
            String calendarId,
            String title,
            ZonedDateTime start,
            ZonedDateTime end,
            String timezone,
            String description,
            boolean canceled) {
        this.id = Objects.requireNonNull(id, "id");
        this.calendarId = Objects.requireNonNull(calendarId, "calendarId");
        this.title = Objects.requireNonNull(title, "title");
        this.start = Objects.requireNonNull(start, "start");
        this.end = Objects.requireNonNull(end, "end");
        this.timezone = Objects.requireNonNull(timezone, "timezone");
        this.description = description;
        this.canceled = canceled;
        if (!start.isBefore(end)) {
            throw new IllegalArgumentException("start must be before end");
        }
    }

    public String getId() {
        return id;
    }

    public String getCalendarId() {
        return calendarId;
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

    public String getDescription() {
        return description;
    }

    public boolean isCanceled() {
        return canceled;
    }

    public CalendarEvent withSchedule(ZonedDateTime newStart, ZonedDateTime newEnd, String newTimezone) {
        return new CalendarEvent(id, calendarId, title, newStart, newEnd, newTimezone, description, canceled);
    }

    public CalendarEvent withCancellation(boolean canceled) {
        return new CalendarEvent(id, calendarId, title, start, end, timezone, description, canceled);
    }
}
