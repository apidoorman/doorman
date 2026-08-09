"""
Rate Limit Simulator

Test rate limits without real traffic. Simulate different scenarios
and preview the impact of rule changes.
"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from models.rate_limit_models import RateLimitRule, RuleType, TimeWindow
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class SimulationRequest:
    """Simulated request"""

    timestamp: datetime
    user_id: str
    endpoint: str
    ip: str


@dataclass
class SimulationResult:
    """Result of simulation"""

    total_requests: int
    allowed_requests: int
    blocked_requests: int
    burst_used_count: int
    success_rate: float
    average_remaining: float
    peak_usage: int
    requests_by_second: dict[int, int]


class RateLimitSimulator:
    """
    Simulate rate limiting scenarios without real traffic
    """

    def __init__(self):
        """Initialize simulator"""
        self.rate_limiter = RateLimiter()

    def generate_requests(
        self, num_requests: int, duration_seconds: int, pattern: str = 'uniform'
    ) -> list[SimulationRequest]:
        """
        Generate simulated requests

        Args:
            num_requests: Number of requests to generate
            duration_seconds: Duration over which to spread requests
            pattern: Distribution pattern (uniform, burst, spike, gradual)

        Returns:
            List of simulated requests
        """
        requests = []
        start_time = datetime.now()

        if pattern == 'uniform':
            # Evenly distributed
            interval = duration_seconds / num_requests
            for i in range(num_requests):
                timestamp = start_time + timedelta(seconds=i * interval)
                requests.append(
                    SimulationRequest(
                        timestamp=timestamp,
                        user_id='sim_user',
                        endpoint='/api/test',
                        ip='192.168.1.1',
                    )
                )

        elif pattern == 'burst':
            # All requests in first 10% of duration
            burst_duration = duration_seconds * 0.1
            interval = burst_duration / num_requests
            for i in range(num_requests):
                timestamp = start_time + timedelta(seconds=i * interval)
                requests.append(
                    SimulationRequest(
                        timestamp=timestamp,
                        user_id='sim_user',
                        endpoint='/api/test',
                        ip='192.168.1.1',
                    )
                )

        elif pattern == 'spike':
            # Spike in the middle
            spike_start = duration_seconds * 0.4
            spike_duration = duration_seconds * 0.2
            interval = spike_duration / num_requests
            for i in range(num_requests):
                timestamp = start_time + timedelta(seconds=spike_start + i * interval)
                requests.append(
                    SimulationRequest(
                        timestamp=timestamp,
                        user_id='sim_user',
                        endpoint='/api/test',
                        ip='192.168.1.1',
                    )
                )

        elif pattern == 'gradual':
            # Gradually increasing rate
            for i in range(num_requests):
                # Quadratic distribution (more requests toward end)
                progress = (i / num_requests) ** 2
                timestamp = start_time + timedelta(seconds=progress * duration_seconds)
                requests.append(
                    SimulationRequest(
                        timestamp=timestamp,
                        user_id='sim_user',
                        endpoint='/api/test',
                        ip='192.168.1.1',
                    )
                )

        elif pattern == 'random':
            # Random distribution
            for i in range(num_requests):
                random_offset = random.uniform(0, duration_seconds)
                timestamp = start_time + timedelta(seconds=random_offset)
                requests.append(
                    SimulationRequest(
                        timestamp=timestamp,
                        user_id='sim_user',
                        endpoint='/api/test',
                        ip='192.168.1.1',
                    )
                )
            # Sort by timestamp
            requests.sort(key=lambda r: r.timestamp)

        return requests

    def simulate_rule(
        self, rule: RateLimitRule, requests: list[SimulationRequest]
    ) -> SimulationResult:
        """
        Simulate rate limit rule against requests

        Args:
            rule: Rate limit rule to test
            requests: List of simulated requests

        Returns:
            Simulation result with statistics
        """
        allowed = 0
        blocked = 0
        burst_used = 0
        remaining_values = []
        requests_by_second = {}

        # Track usage by second
        for request in requests:
            second = int(request.timestamp.timestamp())
            requests_by_second[second] = requests_by_second.get(second, 0) + 1

        # Simulate each request
        for request in requests:
            # In real scenario, would check actual Redis counters
            # For simulation, we'll use simplified logic

            # Calculate current window usage
            window_start = request.timestamp - timedelta(
                seconds=self._get_window_seconds(rule.time_window)
            )
            window_requests = [
                r for r in requests if window_start <= r.timestamp <= request.timestamp
            ]
            current_usage = len(window_requests)

            # Check if within limit
            if current_usage <= rule.limit:
                allowed += 1
                remaining = rule.limit - current_usage
                remaining_values.append(remaining)
            elif rule.burst_allowance > 0 and current_usage <= rule.limit + rule.burst_allowance:
                # Use burst tokens
                allowed += 1
                burst_used += 1
                remaining = rule.limit + rule.burst_allowance - current_usage
                remaining_values.append(remaining)
            else:
                blocked += 1
                remaining_values.append(0)

        # Calculate statistics
        total = len(requests)
        success_rate = (allowed / total * 100) if total > 0 else 0
        avg_remaining = sum(remaining_values) / len(remaining_values) if remaining_values else 0
        peak_usage = max(requests_by_second.values()) if requests_by_second else 0

        return SimulationResult(
            total_requests=total,
            allowed_requests=allowed,
            blocked_requests=blocked,
            burst_used_count=burst_used,
            success_rate=success_rate,
            average_remaining=avg_remaining,
            peak_usage=peak_usage,
            requests_by_second=requests_by_second,
        )

    def _get_window_seconds(self, window: TimeWindow) -> int:
        """Get window duration in seconds"""
        window_map = {
            TimeWindow.SECOND: 1,
            TimeWindow.MINUTE: 60,
            TimeWindow.HOUR: 3600,
            TimeWindow.DAY: 86400,
            TimeWindow.MONTH: 2592000,  # 30 days
        }
        return window_map.get(window, 60)

    def compare_rules(
        self, rules: list[RateLimitRule], requests: list[SimulationRequest]
    ) -> dict[str, SimulationResult]:
        """
        Compare multiple rules against same request pattern

        Args:
            rules: List of rules to compare
            requests: Simulated requests

        Returns:
            Dictionary mapping rule_id to simulation result
        """
        results = {}

        for rule in rules:
            result = self.simulate_rule(rule, requests)
            results[rule.rule_id] = result

        return results

    def preview_rule_change(
        self,
        current_rule: RateLimitRule,
        new_rule: RateLimitRule,
        historical_pattern: str = 'uniform',
        duration_minutes: int = 60,
    ) -> dict[str, SimulationResult]:
        """
        Preview impact of changing a rule

        Args:
            current_rule: Current rule configuration
            new_rule: Proposed new rule configuration
            historical_pattern: Traffic pattern to simulate
            duration_minutes: Duration to simulate

        Returns:
            Comparison of current vs new rule performance
        """
        # Estimate request volume based on current limit
        estimated_requests = int(current_rule.limit * 1.5)  # 150% of limit

        # Generate requests
        requests = self.generate_requests(
            num_requests=estimated_requests,
            duration_seconds=duration_minutes * 60,
            pattern=historical_pattern,
        )

        # Compare rules
        return self.compare_rules([current_rule, new_rule], requests)

    def test_burst_effectiveness(
        self, base_limit: int, burst_allowances: list[int], spike_intensity: float = 2.0
    ) -> dict[int, SimulationResult]:
        """
        Test effectiveness of different burst allowances

        Args:
            base_limit: Base rate limit
            burst_allowances: List of burst allowances to test
            spike_intensity: Multiplier for spike (2.0 = 2x normal rate)

        Returns:
            Results for each burst allowance
        """
        # Generate spike pattern
        spike_requests = int(base_limit * spike_intensity)

        requests = self.generate_requests(
            num_requests=spike_requests, duration_seconds=60, pattern='spike'
        )

        results = {}

        for burst in burst_allowances:
            rule = RateLimitRule(
                rule_id=f'burst_{burst}',
                rule_type=RuleType.PER_USER,
                time_window=TimeWindow.MINUTE,
                limit=base_limit,
                burst_allowance=burst,
            )

            result = self.simulate_rule(rule, requests)
            results[burst] = result

        return results

    def generate_report(self, rule: RateLimitRule, result: SimulationResult) -> str:
        """
        Generate human-readable simulation report

        Args:
            rule: Rule that was simulated
            result: Simulation result

        Returns:
            Formatted report string
        """
        report = f"""
Rate Limit Simulation Report
{'=' * 50}

Rule Configuration:
  Rule ID: {rule.rule_id}
  Type: {rule.rule_type.value}
  Time Window: {rule.time_window.value}
  Limit: {rule.limit}
  Burst Allowance: {rule.burst_allowance}

Simulation Results:
  Total Requests: {result.total_requests}
  Allowed: {result.allowed_requests} ({result.success_rate:.1f}%)
  Blocked: {result.blocked_requests}
  Burst Used: {result.burst_used_count}

Performance Metrics:
  Success Rate: {result.success_rate:.1f}%
  Average Remaining: {result.average_remaining:.1f}
  Peak Usage: {result.peak_usage} req/sec

Recommendation:
"""

        # Add recommendations
        if result.success_rate < 90:
            report += '  ⚠️  Consider increasing limit or burst allowance\n'
        elif result.success_rate > 99 and result.average_remaining > rule.limit * 0.5:
            report += '  ℹ️  Limit may be too high, consider reducing\n'
        else:
            report += '  ✅ Rule configuration appears appropriate\n'

        if result.burst_used_count > 0:
            burst_percentage = result.burst_used_count / result.allowed_requests * 100
            report += f'  ℹ️  {burst_percentage:.1f}% of requests used burst tokens\n'

        return report

    def run_scenario(
        self,
        scenario_name: str,
        rule: RateLimitRule,
        pattern: str = 'uniform',
        duration_minutes: int = 5,
    ) -> dict:
        """
        Run a named simulation scenario

        Args:
            scenario_name: Name of the scenario
            rule: Rule to test
            pattern: Traffic pattern
            duration_minutes: Duration to simulate

        Returns:
            Scenario results with report
        """
        # Generate requests based on rule limit
        num_requests = rule.limit * 2  # 2x the limit

        requests = self.generate_requests(
            num_requests=num_requests, duration_seconds=duration_minutes * 60, pattern=pattern
        )

        result = self.simulate_rule(rule, requests)
        report = self.generate_report(rule, result)

        return {
            'scenario_name': scenario_name,
            'rule': rule,
            'pattern': pattern,
            'result': result,
            'report': report,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def quick_simulate(
    limit: int, time_window: str = 'minute', burst: int = 0, pattern: str = 'uniform'
) -> str:
    """
    Quick simulation helper

    Args:
        limit: Rate limit
        time_window: Time window (second, minute, hour, day)
        burst: Burst allowance
        pattern: Traffic pattern

    Returns:
        Simulation report
    """
    simulator = RateLimitSimulator()

    rule = RateLimitRule(
        rule_id='quick_sim',
        rule_type=RuleType.PER_USER,
        time_window=TimeWindow(time_window),
        limit=limit,
        burst_allowance=burst,
    )

    requests = simulator.generate_requests(
        num_requests=limit * 2, duration_seconds=60, pattern=pattern
    )

    result = simulator.simulate_rule(rule, requests)
    return simulator.generate_report(rule, result)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    # Example: Test different burst allowances
    simulator = RateLimitSimulator()

    print('Testing burst effectiveness...')
    results = simulator.test_burst_effectiveness(
        base_limit=100, burst_allowances=[0, 20, 50, 100], spike_intensity=2.0
    )

    for burst, result in results.items():
        print(f'\nBurst Allowance: {burst}')
        print(f'  Success Rate: {result.success_rate:.1f}%')
        print(f'  Burst Used: {result.burst_used_count}')

    # Example: Preview rule change
    print('\n' + '=' * 50)
    print('Previewing rule change...')

    current = RateLimitRule(
        rule_id='current',
        rule_type=RuleType.PER_USER,
        time_window=TimeWindow.MINUTE,
        limit=100,
        burst_allowance=20,
    )

    proposed = RateLimitRule(
        rule_id='proposed',
        rule_type=RuleType.PER_USER,
        time_window=TimeWindow.MINUTE,
        limit=150,
        burst_allowance=30,
    )

    comparison = simulator.preview_rule_change(current, proposed)

    for rule_id, result in comparison.items():
        print(f'\n{rule_id.upper()}:')
        print(f'  Success Rate: {result.success_rate:.1f}%')
        print(f'  Blocked: {result.blocked_requests}')
