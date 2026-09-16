from pathlib import Path

from gltest.direct import create_address


VAULT = Path(__file__).parents[2] / "contracts" / "demo_vault.py"


def address_text(address):
    if isinstance(address, bytes):
        return "0x" + address.hex()
    return str(address)


def deploy_vault(direct_deploy, direct_owner):
    return direct_deploy(str(VAULT), address_text(direct_owner))


def test_vault_starts_unconfigured_and_unpaused(direct_deploy, direct_owner):
    vault = deploy_vault(direct_deploy, direct_owner)

    state = vault.get_state()

    assert state["paused"] is False
    assert state["controller"] == "0x0000000000000000000000000000000000000000"
    assert state["balance"] == 0
    assert state["total_deposits"] == 0
    assert state["pause_count"] == 0
    assert state["last_action"] == "created"


def test_deposit_records_real_message_value(direct_vm, direct_deploy, direct_owner, direct_alice):
    vault = deploy_vault(direct_deploy, direct_owner)
    direct_vm.sender = direct_alice
    direct_vm.value = 123

    vault.deposit()

    state = vault.get_state()
    assert state["total_deposits"] == 123
    assert state["last_action"] == "deposit"


def test_controller_binding_is_one_time_and_initializer_only(
    direct_vm, direct_deploy, direct_owner, direct_alice
):
    vault = deploy_vault(direct_deploy, direct_owner)
    controller = create_address("circuit-controller")

    with direct_vm.prank(direct_alice), direct_vm.expect_revert("initializer"):
        vault.set_controller(address_text(controller))

    direct_vm.sender = direct_owner
    vault.set_controller(address_text(controller))

    state = vault.get_state()
    assert state["controller"] == address_text(controller)
    assert state["last_action"] == "controller_bound"

    with direct_vm.expect_revert("initializer"):
        vault.set_controller(address_text(direct_alice))


def test_pause_requires_controller_and_is_idempotent(
    direct_vm, direct_deploy, direct_owner, direct_bob
):
    vault = deploy_vault(direct_deploy, direct_owner)
    controller = create_address("circuit-controller")
    direct_vm.sender = direct_owner
    vault.set_controller(address_text(controller))

    with direct_vm.prank(direct_bob), direct_vm.expect_revert("bound controller"):
        vault.pause()

    with direct_vm.prank(controller):
        vault.pause()
        vault.pause()

    state = vault.get_state()
    assert state["paused"] is True
    assert state["pause_count"] == 1
    assert state["last_action"] == "paused"


def test_paused_vault_rejects_deposits(direct_vm, direct_deploy, direct_owner):
    vault = deploy_vault(direct_deploy, direct_owner)
    controller = create_address("circuit-controller")
    direct_vm.sender = direct_owner
    vault.set_controller(address_text(controller))
    with direct_vm.prank(controller):
        vault.pause()

    direct_vm.value = 100
    with direct_vm.expect_revert("vault is paused"):
        vault.deposit()


def test_withdraw_rejects_more_than_live_balance(
    direct_vm, direct_deploy, direct_owner, direct_alice
):
    vault = deploy_vault(direct_deploy, direct_owner)
    vault_address = direct_vm._contract_address
    direct_vm.deal(vault_address, 50)

    with direct_vm.expect_revert("insufficient vault balance"):
        vault.withdraw(51, address_text(direct_alice))
