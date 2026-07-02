"""test_cmd_uplink.py:

Test command dispatcher with basic integration tests.
"""


from pathlib import Path

def test_send_uplink_command(fprime_test_api):
    """Test that commands may be sent

    Tests command send, dispatch, and receipt using send_and_assert command with a pair of CmdDispatcher commands.
    """
    root_dir = Path(__file__).parents[6]

    # file_path = test_seq.seq  and destination = /tmp/test_seq.seq (for fileManager)
    assert fprime_test_api.uplink_file_and_await_completion(
        str(root_dir / "test_seq.seq"), "test_seq.seq", timeout=20
    ), "Failed to uplink test_seq.seq"

    # for fileDownlink
    assert fprime_test_api.uplink_file_and_await_completion(
        str(root_dir / "test_seq_wait.seq"), "test_seq_wait.seq", timeout=20
    ), "Failed to uplink test_seq_wait.seq"

    # for health, fileDownlink, fileManager
    assert fprime_test_api.uplink_file_and_await_completion(
        str(root_dir / "1MiB.txt"), "1MiB.txt", timeout=20
    ), "Failed to uplink 1MiB.txt"
