pub fn api_name_version(name: &str, version: &str, leading_slash: bool) -> String {
    if leading_slash {
        format!("/{name}/{version}")
    } else {
        format!("{name}/{version}")
    }
}
