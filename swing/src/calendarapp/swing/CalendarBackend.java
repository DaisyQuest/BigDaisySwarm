package calendarapp.swing;

import java.time.LocalDate;
import java.time.ZonedDateTime;
import java.util.List;

/**
 * Contract for fetching events. Implementations can wrap the Python backend or in-memory fixtures
 * while keeping the Swing client agnostic to storage concerns.
 */
public interface CalendarBackend {
    List<CalendarEvent> listEvents();

    List<CalendarEvent> listEventsIncludingCanceled();

    List<CalendarEvent> listEventsForDate(LocalDate date);

    List<CalendarEvent> listEventsForCalendar(String calendarId);

    List<CalendarEvent> listEventsForCalendarOnDate(String calendarId, LocalDate date);

    CalendarEvent upsertEvent(CalendarEvent event);

    CalendarEvent cancelEvent(String eventId);

    CalendarEvent rescheduleEvent(String eventId, ZonedDateTime start, ZonedDateTime end, String timezone);
}
