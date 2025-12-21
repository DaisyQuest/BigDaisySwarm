use chrono::{DateTime, FixedOffset, NaiveDate};
use reqwest::Url;
use reqwest::blocking::Client as HttpClient;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Error type for calendar client operations.
#[derive(Debug, Error)]
pub enum ClientError {
    /// The backend returned a non-success status code.
    #[error("backend returned error status {status}: {body}")]
    ApiError { status: u16, body: String },
    /// The backend response could not be parsed into expected structures.
    #[error("invalid response: {0}")]
    InvalidResponse(String),
    /// HTTP-level error when sending the request.
    #[error(transparent)]
    Transport(#[from] reqwest::Error),
    /// The provided base URL was invalid.
    #[error("invalid base url: {0}")]
    InvalidBaseUrl(String),
}

/// Representation of a calendar event used by the Rust client.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CalendarEvent {
    pub id: String,
    pub calendar_id: String,
    pub title: String,
    #[serde(with = "crate::rfc3339")]
    pub start: DateTime<FixedOffset>,
    #[serde(with = "crate::rfc3339")]
    pub end: DateTime<FixedOffset>,
    pub timezone: String,
    pub description: Option<String>,
    pub canceled: bool,
}

#[derive(Debug, Deserialize)]
struct EventsEnvelope {
    events: Vec<RawEvent>,
}

#[derive(Debug, Deserialize, Serialize)]
struct RawEvent {
    id: Option<String>,
    calendar_id: Option<String>,
    title: Option<String>,
    start: Option<String>,
    end: Option<String>,
    timezone: Option<String>,
    description: Option<String>,
    canceled: Option<bool>,
}

mod rfc3339 {
    use chrono::{DateTime, FixedOffset};
    use serde::{Deserialize, Deserializer, Serializer, de};

    pub fn serialize<S>(dt: &DateTime<FixedOffset>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&dt.to_rfc3339())
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<DateTime<FixedOffset>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        DateTime::parse_from_rfc3339(&s).map_err(de::Error::custom)
    }
}

impl TryFrom<RawEvent> for CalendarEvent {
    type Error = ClientError;

    fn try_from(value: RawEvent) -> Result<Self, Self::Error> {
        let id = value
            .id
            .ok_or_else(|| ClientError::InvalidResponse("missing id".to_string()))?;
        let calendar_id = value
            .calendar_id
            .ok_or_else(|| ClientError::InvalidResponse("missing calendar_id".to_string()))?;
        let title = value
            .title
            .ok_or_else(|| ClientError::InvalidResponse("missing title".to_string()))?;
        let timezone = value
            .timezone
            .ok_or_else(|| ClientError::InvalidResponse("missing timezone".to_string()))?;
        let start_str = value
            .start
            .ok_or_else(|| ClientError::InvalidResponse("missing start".to_string()))?;
        let end_str = value
            .end
            .ok_or_else(|| ClientError::InvalidResponse("missing end".to_string()))?;

        let start = DateTime::parse_from_rfc3339(&start_str)
            .map_err(|_| ClientError::InvalidResponse("invalid start datetime".to_string()))?;
        let end = DateTime::parse_from_rfc3339(&end_str)
            .map_err(|_| ClientError::InvalidResponse("invalid end datetime".to_string()))?;

        Ok(CalendarEvent {
            id,
            calendar_id,
            title,
            start,
            end,
            timezone,
            description: value.description,
            canceled: value.canceled.unwrap_or(false),
        })
    }
}

/// Minimal REST client for the calendar backend.
#[derive(Clone, Debug)]
pub struct CalendarClient {
    http: HttpClient,
    base_url: Url,
}

impl CalendarClient {
    /// Create a new client with the given base URL.
    pub fn new(base_url: &str) -> Result<Self, ClientError> {
        let http = HttpClient::builder().no_proxy().build()?;
        let base_url =
            Url::parse(base_url).map_err(|e| ClientError::InvalidBaseUrl(e.to_string()))?;
        Ok(Self { http, base_url })
    }

    /// List all active events.
    pub fn list_events(&self) -> Result<Vec<CalendarEvent>, ClientError> {
        self.fetch_events(false, None, None, false)
    }

    /// List all events including canceled entries.
    pub fn list_events_including_canceled(&self) -> Result<Vec<CalendarEvent>, ClientError> {
        self.fetch_events(true, None, None, true)
    }

    /// List active events for a specific calendar.
    pub fn list_events_for_calendar(
        &self,
        calendar_id: &str,
    ) -> Result<Vec<CalendarEvent>, ClientError> {
        self.fetch_events(false, Some(calendar_id), None, false)
    }

    /// List active events on a specific date.
    pub fn list_events_for_date(&self, date: NaiveDate) -> Result<Vec<CalendarEvent>, ClientError> {
        self.fetch_events(false, None, Some(date), false)
    }

    /// List active events for a calendar on a specific date.
    pub fn list_events_for_calendar_on_date(
        &self,
        calendar_id: &str,
        date: NaiveDate,
    ) -> Result<Vec<CalendarEvent>, ClientError> {
        self.fetch_events(false, Some(calendar_id), Some(date), false)
    }

    /// Create or update an event via PUT /events/{id}.
    pub fn upsert_event(&self, event: &CalendarEvent) -> Result<CalendarEvent, ClientError> {
        let mut url = self.base_url.clone();
        url.set_path(&format!("/events/{}", event.id));

        let response = self.http.put(url).json(event).send()?;
        self.parse_event_response(response)
    }

    /// Cancel an event.
    pub fn cancel_event(&self, event_id: &str) -> Result<CalendarEvent, ClientError> {
        self.perform_event_action(event_id, "cancel", serde_json::Value::Null)
    }

    /// Reschedule an event occurrence.
    pub fn reschedule_event(
        &self,
        event_id: &str,
        start: DateTime<FixedOffset>,
        end: DateTime<FixedOffset>,
        timezone: &str,
    ) -> Result<CalendarEvent, ClientError> {
        let payload = serde_json::json!({
            "start": start.to_rfc3339(),
            "end": end.to_rfc3339(),
            "timezone": timezone,
        });
        self.perform_event_action(event_id, "reschedule", payload)
    }

    fn perform_event_action(
        &self,
        event_id: &str,
        action: &str,
        body: serde_json::Value,
    ) -> Result<CalendarEvent, ClientError> {
        let mut url = self.base_url.clone();
        url.set_path(&format!("/events/{}/{}", event_id, action));
        let request = self.http.post(url);
        let response = if body.is_null() {
            request.send()?
        } else {
            request.json(&body).send()?
        };
        self.parse_event_response(response)
    }

    fn fetch_events(
        &self,
        include_canceled: bool,
        calendar_id: Option<&str>,
        date: Option<NaiveDate>,
        preserve_canceled: bool,
    ) -> Result<Vec<CalendarEvent>, ClientError> {
        let mut url = self.base_url.clone();
        url.set_path("/events");
        let mut pairs = url.query_pairs_mut();
        pairs.append_pair("includeCanceled", &include_canceled.to_string());
        if let Some(calendar_id) = calendar_id {
            pairs.append_pair("calendarId", calendar_id);
        }
        if let Some(date) = date {
            pairs.append_pair("date", &date.to_string());
        }
        drop(pairs);

        let response = self.http.get(url).send()?;
        if !response.status().is_success() {
            let status = response.status().as_u16();
            let body = response.text().unwrap_or_default();
            return Err(ClientError::ApiError { status, body });
        }
        let envelope: EventsEnvelope = response.json().map_err(|e| {
            ClientError::InvalidResponse(format!("unable to parse events payload: {e}"))
        })?;
        let mut events: Vec<CalendarEvent> = envelope
            .events
            .into_iter()
            .map(CalendarEvent::try_from)
            .collect::<Result<_, _>>()?;
        if !preserve_canceled {
            events.retain(|event| !event.canceled);
        }
        events.sort_by_key(|event| event.start);
        Ok(events)
    }

    fn parse_event_response(
        &self,
        response: reqwest::blocking::Response,
    ) -> Result<CalendarEvent, ClientError> {
        if !response.status().is_success() {
            let status = response.status().as_u16();
            let body = response.text().unwrap_or_default();
            return Err(ClientError::ApiError { status, body });
        }
        let raw: RawEvent = response.json().map_err(|e| {
            ClientError::InvalidResponse(format!("unable to parse event payload: {e}"))
        })?;
        CalendarEvent::try_from(raw)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Utc};
    use httpmock::MockServer;
    use reqwest::StatusCode;

    fn sample_event(id: &str) -> CalendarEvent {
        CalendarEvent {
            id: id.to_string(),
            calendar_id: "team".to_string(),
            title: "Kickoff".to_string(),
            start: Utc
                .with_ymd_and_hms(2025, 1, 10, 15, 0, 0)
                .unwrap()
                .with_timezone(&FixedOffset::east_opt(0).unwrap()),
            end: Utc
                .with_ymd_and_hms(2025, 1, 10, 16, 0, 0)
                .unwrap()
                .with_timezone(&FixedOffset::east_opt(0).unwrap()),
            timezone: "UTC".to_string(),
            description: Some("Start".to_string()),
            canceled: false,
        }
    }

    #[test]
    fn list_events_filters_canceled_and_sorts() {
        let server = MockServer::start();
        let payload = serde_json::json!({
            "events": [
                {"id":"2","calendar_id":"team","title":"Later","start":"2025-01-10T16:00:00Z","end":"2025-01-10T17:00:00Z","timezone":"UTC","canceled":false},
                {"id":"1","calendar_id":"team","title":"Cancel","start":"2025-01-09T15:00:00Z","end":"2025-01-09T16:00:00Z","timezone":"UTC","canceled":true}
            ]
        });
        let mock = server.mock(|when, then| {
            when.method("GET")
                .path("/events")
                .query_param("includeCanceled", "false");
            then.status(200).json_body(payload);
        });

        let client = CalendarClient::new(&server.base_url()).unwrap();
        let events = client.list_events().unwrap();
        mock.assert();
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].id, "2");
        assert_eq!(events[0].start.to_rfc3339(), "2025-01-10T16:00:00+00:00");
    }

    #[test]
    fn list_events_including_canceled_preserves_flag() {
        let server = MockServer::start();
        let payload = serde_json::json!({
            "events": [
                {"id":"a","calendar_id":"team","title":"Active","start":"2025-01-10T15:00:00Z","end":"2025-01-10T16:00:00Z","timezone":"UTC","canceled":false},
                {"id":"b","calendar_id":"team","title":"Canceled","start":"2025-01-10T17:00:00Z","end":"2025-01-10T18:00:00Z","timezone":"UTC","canceled":true}
            ]
        });
        server.mock(|when, then| {
            when.method("GET")
                .path("/events")
                .query_param("includeCanceled", "true");
            then.status(200).json_body(payload);
        });

        let client = CalendarClient::new(&server.base_url()).unwrap();
        let events = client.list_events_including_canceled().unwrap();
        assert_eq!(events.len(), 2);
        assert!(events.iter().any(|e| e.canceled));
    }

    #[test]
    fn list_events_supports_calendar_and_date_filters() {
        let server = MockServer::start();
        server.mock(|when, then| {
            when.method("GET")
                .path("/events")
                .query_param("includeCanceled", "false")
                .query_param("calendarId", "team")
                .query_param("date", "2025-01-10");
            then.status(200).json_body(serde_json::json!({
                "events": [
                    {"id":"kickoff","calendar_id":"team","title":"Kickoff","start":"2025-01-10T15:00:00Z","end":"2025-01-10T16:00:00Z","timezone":"UTC","description":"Start","canceled":false}
                ]
            }));
        });

        let client = CalendarClient::new(&server.base_url()).unwrap();
        let events = client
            .list_events_for_calendar_on_date("team", NaiveDate::from_ymd_opt(2025, 1, 10).unwrap())
            .unwrap();
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].description.as_deref(), Some("Start"));
    }

    #[test]
    fn upsert_reschedule_and_cancel_round_trip() {
        let server = MockServer::start();
        let event = sample_event("kickoff");

        let upsert_mock = server.mock(|when, then| {
            when.method("PUT")
                .path("/events/kickoff")
                .json_body_obj(&event);
            then.status(200).json_body(serde_json::json!({
                "id":"kickoff","calendar_id":"team","title":"Kickoff","start":"2025-01-10T15:00:00Z","end":"2025-01-10T16:00:00Z","timezone":"UTC","description":"Start","canceled":false
            }));
        });

        let reschedule_mock = server.mock(|when, then| {
            when.method("POST")
                .path("/events/kickoff/reschedule")
                .json_body(serde_json::json!({
                    "start":"2025-01-10T17:00:00+00:00",
                    "end":"2025-01-10T18:00:00+00:00",
                    "timezone":"UTC"
                }));
            then.status(200).json_body(serde_json::json!({
                "id":"kickoff","calendar_id":"team","title":"Kickoff","start":"2025-01-10T17:00:00Z","end":"2025-01-10T18:00:00Z","timezone":"UTC","description":"Start","canceled":false
            }));
        });

        let cancel_mock = server.mock(|when, then| {
            when.method("POST")
                .path("/events/kickoff/cancel");
            then.status(200).json_body(serde_json::json!({
                "id":"kickoff","calendar_id":"team","title":"Kickoff","start":"2025-01-10T17:00:00Z","end":"2025-01-10T18:00:00Z","timezone":"UTC","canceled":true
            }));
        });

        let client = CalendarClient::new(&server.base_url()).unwrap();
        let upserted = client.upsert_event(&event).unwrap();
        upsert_mock.assert();
        assert_eq!(upserted.id, event.id);

        let start = DateTime::parse_from_rfc3339("2025-01-10T17:00:00+00:00").unwrap();
        let end = DateTime::parse_from_rfc3339("2025-01-10T18:00:00+00:00").unwrap();
        let rescheduled = client
            .reschedule_event("kickoff", start, end, "UTC")
            .unwrap();
        reschedule_mock.assert();
        assert_eq!(rescheduled.start, start);

        let canceled = client.cancel_event("kickoff").unwrap();
        cancel_mock.assert();
        assert!(canceled.canceled);
    }

    #[test]
    fn reports_backend_and_parsing_errors() {
        let server = MockServer::start();
        server.mock(|when, then| {
            when.method("GET").path("/events");
            then.status(StatusCode::INTERNAL_SERVER_ERROR.as_u16())
                .body("boom");
        });
        let client = CalendarClient::new(&server.base_url()).unwrap();
        let err = client.list_events().unwrap_err();
        match err {
            ClientError::ApiError { status, body } => {
                assert_eq!(status, 500);
                assert_eq!(body, "boom");
            }
            other => panic!("unexpected error: {other:?}"),
        }

        let server = MockServer::start();
        server.mock(|when, then| {
            when.method("GET").path("/events");
            then.status(200).body("not-json");
        });
        let client = CalendarClient::new(&server.base_url()).unwrap();
        let err = client.list_events_including_canceled().unwrap_err();
        assert!(matches!(err, ClientError::InvalidResponse(_)));
    }

    #[test]
    fn rejects_invalid_event_payloads() {
        let server = MockServer::start();
        server.mock(|when, then| {
            when.method("GET").path("/events");
            then.status(200).json_body(serde_json::json!({
                "events": [
                    {"calendar_id":"team","title":"Kickoff","start":"bad","end":"also-bad","timezone":"UTC"}
                ]
            }));
        });
        let client = CalendarClient::new(&server.base_url()).unwrap();
        let err = client.list_events().unwrap_err();
        assert!(matches!(err, ClientError::InvalidResponse(_)));
    }
}
