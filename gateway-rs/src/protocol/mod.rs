pub mod crud;
pub mod graphql;
pub mod grpc;
pub mod rest;
pub mod soap;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Protocol {
    Rest,
    Soap,
    Graphql,
    Grpc,
}
