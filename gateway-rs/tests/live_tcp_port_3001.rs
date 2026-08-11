//! TCP Live Test Suite
//! Runs real HTTP/TCP socket requests against a server running on http://localhost:3001.

use reqwest::{Client, StatusCode};
use serde_json::{Value, json};

fn target_url() -> String {
    std::env::var("LIVE_SERVER_URL").unwrap_or_else(|_| "http://localhost:3001".to_owned())
}

#[tokio::test]
#[ignore = "requires a separately running gateway; use make test-live-tcp"]
async fn test_tcp_live_server_liveness_readiness_and_auth() {
    let base = target_url();
    let client = Client::new();

    // 1. Check Liveness over TCP socket
    let res = match client
        .get(format!("{base}/platform/monitor/liveness"))
        .send()
        .await
    {
        Ok(res) => res,
        Err(err) => {
            panic!(
                "\n\n❌ LIVE SERVER NOT ACCESSIBLE ON {base}!\nError: {err}\n\nPlease start the gateway server on port 3001 (e.g. `docker compose up` or `cargo run`) before running TCP live tests.\n"
            );
        }
    };
    assert_eq!(res.status(), StatusCode::OK);
    let body: Value = res.json().await.unwrap();
    assert_eq!(body["status"], "alive");

    // 2. Check Readiness over TCP socket
    let res = client
        .get(format!("{base}/platform/monitor/readiness"))
        .send()
        .await
        .unwrap();
    assert_eq!(res.status(), StatusCode::OK);

    // 3. Admin Login over TCP socket
    let admin_email =
        std::env::var("DOORMAN_ADMIN_EMAIL").unwrap_or_else(|_| "admin@doorman.dev".to_owned());
    let admin_password =
        std::env::var("DOORMAN_ADMIN_PASSWORD").unwrap_or_else(|_| "AdminPassword123!".to_owned());

    let login_res = client
        .post(format!("{base}/platform/authorization"))
        .json(&json!({
            "email": admin_email,
            "password": admin_password
        }))
        .send()
        .await
        .unwrap();

    let status = login_res.status();
    assert!(
        status.is_success(),
        "Failed admin login against live server at {base} (Status: {status})"
    );

    let login_body: Value = login_res.json().await.unwrap();
    let token = login_body["access_token"]
        .as_str()
        .expect("access_token in login response");

    // 4. Authenticated Status Check over TCP socket
    let status_res = client
        .get(format!("{base}/platform/authorization/status"))
        .bearer_auth(token)
        .send()
        .await
        .unwrap();
    assert_eq!(status_res.status(), StatusCode::OK);

    // 5. User Profile Me Check over TCP socket
    let me_res = client
        .get(format!("{base}/platform/user/me"))
        .bearer_auth(token)
        .send()
        .await
        .unwrap();
    assert_eq!(me_res.status(), StatusCode::OK);

    // 6. Security Settings Check over TCP socket
    let sec_res = client
        .get(format!("{base}/platform/security/settings"))
        .bearer_auth(token)
        .send()
        .await
        .unwrap();
    assert_eq!(sec_res.status(), StatusCode::OK);

    // 7. CORS Tool Check over TCP socket
    let cors_res = client
        .post(format!("{base}/platform/tools/cors/check"))
        .bearer_auth(token)
        .json(&json!({"origin": "http://localhost:3000", "method": "GET"}))
        .send()
        .await
        .unwrap();
    assert_eq!(cors_res.status(), StatusCode::OK);
}
