package calendarapp.swing;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Objects;

/**
 * Minimal Swing client that renders calendar events in a table.
 */
public class CalendarSwingClient {
    private final CalendarBackend backend;
    private final DefaultTableModel tableModel;
    private final JTable table;
    private final JPanel rootPanel;
    private final JFrame frame;
    private final DateTimeFormatter formatter = DateTimeFormatter.ISO_OFFSET_DATE_TIME;

    public CalendarSwingClient(CalendarBackend backend) {
        this(backend, !GraphicsEnvironment.isHeadless());
    }

    public CalendarSwingClient(CalendarBackend backend, boolean createWindow) {
        this.backend = Objects.requireNonNull(backend, "backend");
        this.tableModel = new DefaultTableModel(new Object[]{"Title", "Start", "End", "Timezone"}, 0) {
            @Override
            public boolean isCellEditable(int row, int column) {
                return false;
            }
        };
        this.table = new JTable(tableModel);
        this.rootPanel = new JPanel(new BorderLayout());
        this.rootPanel.add(new JScrollPane(table), BorderLayout.CENTER);

        if (createWindow && !GraphicsEnvironment.isHeadless()) {
            JFrame jFrame = new JFrame("Calendar Client");
            jFrame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
            jFrame.setContentPane(rootPanel);
            jFrame.setSize(720, 360);
            this.frame = jFrame;
        } else {
            this.frame = null;
        }
    }

    public void showWindow() {
        if (frame != null) {
            frame.setVisible(true);
        }
    }

    public void loadAllEvents() {
        refreshTable(backend.listEvents());
    }

    public void filterByDate(LocalDate date) {
        refreshTable(backend.listEventsForDate(date));
    }

    JTable getTable() {
        return table;
    }

    DefaultTableModel getTableModel() {
        return tableModel;
    }

    JPanel getRootPanel() {
        return rootPanel;
    }

    void refreshTable(List<CalendarEvent> events) {
        tableModel.setRowCount(0);
        for (CalendarEvent event : events) {
            tableModel.addRow(new Object[]{
                    event.getTitle(),
                    formatter.format(event.getStart()),
                    formatter.format(event.getEnd()),
                    event.getTimezone()
            });
        }
    }
}
