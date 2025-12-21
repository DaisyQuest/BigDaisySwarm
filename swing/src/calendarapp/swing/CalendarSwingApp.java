package calendarapp.swing;

import javax.swing.*;

public final class CalendarSwingApp {
    private CalendarSwingApp() {}

    public static void main(String[] args) {
        System.setProperty("java.awt.headless", "false");
        SwingUtilities.invokeLater(() -> {
            CalendarSwingClient client = new CalendarSwingClient(InMemoryCalendarBackend.sampleData());
            client.loadAllEvents();
            client.showWindow();
        });
    }
}
