package calendarapp.swing;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

/**
 * Simple in-memory backend for the Swing client. Useful for demos and tests.
 */
public final class InMemoryCalendarBackend implements CalendarBackend {
    private final List<CalendarEvent> events;

    public InMemoryCalendarBackend(List<CalendarEvent> events) {
        Objects.requireNonNull(events, "events");
        this.events = new ArrayList<>(events);
        this.events.sort(Comparator.comparing(CalendarEvent::getStart));
    }

    @Override
    public List<CalendarEvent> listEvents() {
        return Collections.unmodifiableList(events);
    }

    @Override
    public List<CalendarEvent> listEventsForDate(LocalDate date) {
        if (date == null) {
            return listEvents();
        }
        List<CalendarEvent> matches = new ArrayList<>();
        for (CalendarEvent event : events) {
            if (event.getStart().toLocalDate().equals(date)) {
                matches.add(event);
            }
        }
        return Collections.unmodifiableList(matches);
    }

    public static InMemoryCalendarBackend sampleData() {
        ZoneId utc = ZoneId.of("UTC");
        List<CalendarEvent> seed = List.of(
                new CalendarEvent(
                        "kickoff",
                        "Kickoff Meeting",
                        ZonedDateTime.of(2025, 1, 10, 15, 0, 0, 0, utc),
                        ZonedDateTime.of(2025, 1, 10, 16, 0, 0, 0, utc),
                        "UTC"),
                new CalendarEvent(
                        "retro",
                        "Retrospective",
                        ZonedDateTime.of(2025, 1, 20, 12, 0, 0, 0, utc),
                        ZonedDateTime.of(2025, 1, 20, 13, 0, 0, 0, utc),
                        "UTC"),
                new CalendarEvent(
                        "planning",
                        "Planning",
                        ZonedDateTime.of(2025, 1, 17, 18, 0, 0, 0, utc),
                        ZonedDateTime.of(2025, 1, 17, 19, 30, 0, 0, utc),
                        "UTC"));
        return new InMemoryCalendarBackend(seed);
    }
}
