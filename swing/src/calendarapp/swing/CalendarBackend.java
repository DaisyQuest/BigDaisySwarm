package calendarapp.swing;

import java.time.LocalDate;
import java.util.List;

/**
 * Contract for fetching events. Implementations can wrap the Python backend or in-memory fixtures
 * while keeping the Swing client agnostic to storage concerns.
 */
public interface CalendarBackend {
    List<CalendarEvent> listEvents();

    List<CalendarEvent> listEventsForDate(LocalDate date);
}
