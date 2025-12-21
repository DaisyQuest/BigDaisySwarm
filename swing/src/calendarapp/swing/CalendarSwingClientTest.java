package calendarapp.swing;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.time.LocalDate;
import java.util.List;

/**
 * Lightweight test harness that exercises the Swing client and backend without external tooling.
 */
public final class CalendarSwingClientTest {
    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        testBackendFiltersAndSorts();
        testClientPopulatesTable();
        testClientClearsTableOnEmptyFilter();
        testRejectsInvalidEventDurations();
        testTableIsReadOnly();
        System.out.println("Swing client tests passed");
    }

    private static void testBackendFiltersAndSorts() {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        List<CalendarEvent> all = backend.listEvents();
        if (all.size() != 3) {
            throw new AssertionError("Expected 3 events, got " + all.size());
        }
        if (!all.get(0).getId().equals("kickoff")) {
            throw new AssertionError("Events should be sorted by start time");
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

    private static void testClientPopulatesTable() throws Exception {
        InMemoryCalendarBackend backend = InMemoryCalendarBackend.sampleData();
        CalendarSwingClient client = new CalendarSwingClient(backend, false);
        SwingUtilities.invokeAndWait(client::loadAllEvents);
        DefaultTableModel model = client.getTableModel();
        if (model.getRowCount() != 3) {
            throw new AssertionError("Expected table to contain all events");
        }
        Object title = model.getValueAt(0, 0);
        if (!"Kickoff Meeting".equals(title)) {
            throw new AssertionError("First event title mismatch");
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
                    "Broken",
                    InMemoryCalendarBackend.sampleData().listEvents().get(0).getEnd(),
                    InMemoryCalendarBackend.sampleData().listEvents().get(0).getStart(),
                    "UTC");
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
}
