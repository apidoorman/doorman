#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct RequestSizes {
    pub bytes_in: u64,
    pub bytes_out: u64,
}
