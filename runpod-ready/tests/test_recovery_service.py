from services.recovery_service import RecoveryService


def test_recreate_by_number() -> None:
    service = RecoveryService(recreate_numbers={3})
    decision = service.should_recreate(number=3, user_id="user01", pod=None)
    assert decision.recreate is True
    assert decision.reason == "number"


def test_recreate_by_id() -> None:
    service = RecoveryService(recreate_ids={"user02"})
    decision = service.should_recreate(number=2, user_id="USER02", pod=None)
    assert decision.recreate is True
    assert decision.reason == "id"


def test_recreate_if_unhealthy() -> None:
    service = RecoveryService(recreate_if_unhealthy=True)
    pod = {"status": "stopped"}
    decision = service.should_recreate(number=2, user_id="user02", pod=pod)
    assert decision.recreate is True
    assert decision.reason == "unhealthy"


def test_no_recreate_when_healthy() -> None:
    service = RecoveryService(recreate_if_unhealthy=True)
    pod = {"status": "running"}
    decision = service.should_recreate(number=2, user_id="user02", pod=pod)
    assert decision.recreate is False
