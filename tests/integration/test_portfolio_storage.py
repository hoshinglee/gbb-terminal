from gbb_terminal.portfolio.models import (
    PortfolioContextInput,
    PortfolioPositionInput,
    RiskPolicyInput,
)
from gbb_terminal.portfolio.repository import PortfolioRepository
from gbb_terminal.storage.database import LocalMarketStore


def policy(name: str, max_position: float) -> RiskPolicyInput:
    return RiskPolicyInput(
        name=name,
        normal_target_position_percent=8,
        max_single_name_exposure_percent=max_position,
        max_assignment_exposure_percent=12,
        max_short_option_collateral_percent=20,
        min_unencumbered_cash_reserve_amount=80_000,
        portfolio_stress_loss_ceiling_percent=25,
    )


def test_portfolio_policy_positions_and_snapshots_survive_database_reopen(tmp_path):
    path = tmp_path / "portfolio.duckdb"
    store = LocalMarketStore(path)
    repository = PortfolioRepository(store.connection)
    repository.save_context(PortfolioContextInput(investable_value=500_000, liquid_cash=150_000))
    position = repository.save_position(
        PortfolioPositionInput(
            ticker="NVDA",
            shares=120,
            cost_basis_per_share=145.25,
            manual_market_value=23_400,
            notes="Manual context remains authoritative when quotes fail.",
        ),
        company_id=None,
    )
    repository.save_context(PortfolioContextInput(investable_value=550_000, liquid_cash=175_000))
    first = repository.save_policy(policy("Personal Policy", 15))
    snapshot = repository.snapshot_current_policy()
    second = repository.save_policy(policy("Personal Policy", 18))
    store.connection.close()

    reopened = LocalMarketStore(path)
    restored = PortfolioRepository(reopened.connection)

    assert restored.get_context().investable_value == 550_000
    assert restored.get_context().liquid_cash == 175_000
    assert restored.get_position(position.position_id).manual_market_value == 23_400
    assert restored.get_position(position.position_id).identity_status == "unresolved"
    assert restored.current_policy().version == 2
    assert restored.current_policy().supersedes_policy_id == first.policy_id
    assert second.max_single_name_exposure_percent == 18
    restored_snapshot = restored.get_policy_snapshot(snapshot.snapshot_id)
    assert restored_snapshot.policy_version == 1
    assert restored_snapshot.policy.max_single_name_exposure_percent == 15
