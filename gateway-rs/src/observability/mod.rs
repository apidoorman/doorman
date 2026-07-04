pub mod audit;
pub mod logging;
pub mod metrics;

pub fn init() {
    logging::init();
}
