//! Safe SOAP body conversion used by endpoint validation.

use quick_xml::{Reader, events::Event};
use serde_json::{Map, Value};

#[derive(Debug)]
struct Node {
    name: String,
    text: Option<String>,
    children: Vec<Node>,
}

pub fn soap_body_object(xml: &str) -> Result<Value, String> {
    let lower = xml.to_ascii_lowercase();
    if lower.contains("<!doctype") || lower.contains("<!entity") {
        return Err("XML DTD/entities are not allowed".to_owned());
    }
    let root = parse(xml)?;
    let body = find_named(&root, "Body").ok_or_else(|| "SOAP Body not found".to_owned())?;
    let operation = body
        .children
        .first()
        .ok_or_else(|| "SOAP Body not found".to_owned())?;
    Ok(Value::Object(children_to_object(operation)))
}

fn parse(xml: &str) -> Result<Node, String> {
    let mut reader = Reader::from_str(xml);
    reader.config_mut().trim_text(true);
    let mut stack = Vec::<Node>::new();
    let mut root = None;
    loop {
        match reader.read_event() {
            Ok(Event::Start(event)) => stack.push(Node {
                name: local_name(event.name().as_ref()),
                text: None,
                children: Vec::new(),
            }),
            Ok(Event::Empty(event)) => {
                let node = Node {
                    name: local_name(event.name().as_ref()),
                    text: None,
                    children: Vec::new(),
                };
                if let Some(parent) = stack.last_mut() {
                    parent.children.push(node);
                } else {
                    root = Some(node);
                }
            }
            Ok(Event::Text(event)) => {
                if let Some(node) = stack.last_mut() {
                    let text = event
                        .decode()
                        .map_err(|_| "Invalid SOAP envelope".to_owned())?
                        .into_owned();
                    if !text.is_empty() {
                        node.text = Some(text);
                    }
                }
            }
            Ok(Event::End(_)) => {
                let node = stack
                    .pop()
                    .ok_or_else(|| "Invalid SOAP envelope".to_owned())?;
                if let Some(parent) = stack.last_mut() {
                    parent.children.push(node);
                } else {
                    root = Some(node);
                }
            }
            Ok(Event::DocType(_)) => return Err("XML DTD/entities are not allowed".to_owned()),
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(_) => return Err("Invalid SOAP envelope".to_owned()),
        }
    }
    if !stack.is_empty() {
        return Err("Invalid SOAP envelope".to_owned());
    }
    root.ok_or_else(|| "Invalid SOAP envelope".to_owned())
}

fn local_name(name: &[u8]) -> String {
    let name = String::from_utf8_lossy(name);
    name.rsplit(':').next().unwrap_or(&name).to_owned()
}

fn find_named<'a>(node: &'a Node, name: &str) -> Option<&'a Node> {
    if node.name == name {
        return Some(node);
    }
    node.children
        .iter()
        .find_map(|child| find_named(child, name))
}

fn children_to_object(node: &Node) -> Map<String, Value> {
    let mut output = Map::new();
    for child in &node.children {
        let value = if child.children.is_empty() {
            child
                .text
                .as_ref()
                .map_or(Value::Null, |text| Value::String(text.clone()))
        } else {
            Value::Object(children_to_object(child))
        };
        // Python's legacy converter overwrites duplicate sibling names.
        output.insert(child.name.clone(), value);
    }
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn converts_first_soap_body_operation_like_python() {
        let xml = r#"<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><Create><user><name>Ada</name></user></Create></soap:Body></soap:Envelope>"#;
        assert_eq!(
            soap_body_object(xml).unwrap(),
            serde_json::json!({"user": {"name": "Ada"}})
        );
    }

    #[test]
    fn rejects_dtd_and_missing_bodies_when_validation_is_enabled() {
        assert!(soap_body_object("<!DOCTYPE x><x/>").is_err());
        assert!(soap_body_object("<Envelope/>").is_err());
    }
}
