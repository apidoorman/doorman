//! GraphQL validation port: depth, complexity field cost, and introspection control.

#[derive(Debug, Clone)]
pub struct GraphqlValidationConfig {
    pub max_depth: usize,
    pub max_cost: usize,
    pub allow_introspection: bool,
}

impl Default for GraphqlValidationConfig {
    fn default() -> Self {
        Self {
            max_depth: 10,
            max_cost: 500,
            allow_introspection: true,
        }
    }
}

pub fn validate_graphql_query(query: &str, config: &GraphqlValidationConfig) -> Result<(), String> {
    if !config.allow_introspection && (query.contains("__schema") || query.contains("__type")) {
        return Err("GraphQL introspection query is prohibited by security policy".to_owned());
    }

    let depth = calculate_graphql_depth(query);
    if depth > config.max_depth {
        return Err(format!(
            "GraphQL query depth {depth} exceeds limit of {}",
            config.max_depth
        ));
    }

    let cost = calculate_graphql_cost(query);
    if cost > config.max_cost {
        return Err(format!(
            "GraphQL query estimated complexity {cost} exceeds limit of {}",
            config.max_cost
        ));
    }

    Ok(())
}

pub fn calculate_graphql_depth(query: &str) -> usize {
    let mut depth = 0usize;
    let mut max_depth = 0usize;
    let mut in_string = false;
    let mut in_comment = false;

    for ch in query.chars() {
        if in_comment {
            if ch == '\n' {
                in_comment = false;
            }
            continue;
        }
        if ch == '"' {
            in_string = !in_string;
            continue;
        }
        if in_string {
            continue;
        }
        if ch == '#' {
            in_comment = true;
            continue;
        }
        if ch == '{' {
            depth += 1;
            if depth > max_depth {
                max_depth = depth;
            }
        } else if ch == '}' {
            depth = depth.saturating_sub(1);
        }
    }

    max_depth
}

pub fn calculate_graphql_cost(query: &str) -> usize {
    let mut cost = 0usize;

    for word in query.split_whitespace() {
        let clean_word = word
            .trim_matches(|c| c == '{' || c == '}' || c == '(' || c == ')' || c == ':' || c == ',');
        if clean_word.starts_with('#') {
            continue;
        }
        if !clean_word.is_empty() && !clean_word.starts_with('"') && !is_graphql_keyword(clean_word)
        {
            cost += 1;
        }
    }

    cost.max(1)
}

fn is_graphql_keyword(word: &str) -> bool {
    matches!(
        word,
        "query" | "mutation" | "subscription" | "fragment" | "on"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_depth_and_cost() {
        let config = GraphqlValidationConfig {
            max_depth: 3,
            max_cost: 10,
            allow_introspection: false,
        };
        let query = "query { user { id name } }";
        assert!(validate_graphql_query(query, &config).is_ok());

        let introspection = "query { __schema { types { name } } }";
        assert!(validate_graphql_query(introspection, &config).is_err());
    }
}
