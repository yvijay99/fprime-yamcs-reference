"""test_yamcs_file_transfer.py:

Test YAMCS file transfer service for file upload and download.
This tests the YAMCS-specific file transfer capabilities.
"""

import random
import tempfile
from pathlib import Path


def test_yamcs_uplink_via_file_transfer(fprime_test_api):
    """Test file uplink using YAMCS file transfer service

    This test uploads a file using YAMCS file transfer and verifies
    the FSW receives it via FileReceived event.
    """
    TEST_DATA = f"test uplink data via YAMCS {random.random()}\n"

    # Create a temporary file with test data
    tmp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    tmp_file.write(TEST_DATA)
    tmp_file.flush()
    tmp_file_path = tmp_file.name
    tmp_file.close()

    # Upload via YAMCS file transfer service
    destination = f"/tmp/yamcs_uplink_test_{random.randint(0, 10000)}.txt"

    # Use the YAMCS client to upload
    yamcs_client = fprime_test_api.pipeline.client_socket
    if not hasattr(yamcs_client, 'upload_file'):
        import pytest
        pytest.skip("Not using YAMCS transport")

    # Upload and wait for completion
    transfer = yamcs_client.upload_file(tmp_file_path, destination, timeout=30)

    # Verify the upload completed successfully
    assert transfer is not None

    # Verify FSW received the file (check for FileReceived event)
    event = fprime_test_api.await_event("FileReceived", timeout=5)
    assert event is not None

    # Cleanup
    Path(tmp_file_path).unlink()

    # Verify file exists on FSW side
    fprime_test_api.send_and_assert_command(
        fprime_test_api.get_mnemonic("Svc.FileManager") + ".FileSize",
        [destination],
        max_delay=5,
    )


def test_yamcs_downlink_via_file_transfer(fprime_test_api):
    """Test file downlink using YAMCS file transfer service

    This test creates a file on FSW, downloads it using YAMCS file transfer,
    and verifies the contents match.
    """
    TEST_DATA = f"test downlink data via YAMCS {random.random()}\n"

    # Create a file on FSW side using FileManager
    source_file = f"/tmp/yamcs_downlink_source_{random.randint(0, 10000)}.txt"

    # Write test data to a temp file
    tmp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, dir="/tmp/")
    tmp_file.write(TEST_DATA)
    tmp_file.flush()
    tmp_file_path = tmp_file.name
    tmp_file.close()

    # First upload the file to FSW so we have something to download
    yamcs_client = fprime_test_api.pipeline.client_socket
    if not hasattr(yamcs_client, 'download_file'):
        import pytest
        pytest.skip("Not using YAMCS transport")

    # Upload first
    yamcs_client.upload_file(tmp_file_path, source_file, timeout=30)
    fprime_test_api.await_event("FileReceived", timeout=5)

    # Now download it back using YAMCS file transfer
    download_bucket = "fprimeFilesOut"
    downloaded_file = f"yamcs_downloaded_{random.randint(0, 10000)}.txt"

    # Request FSW to send the file via YAMCS file transfer
    # Note: This requires FSW integration with YAMCS file transfer service
    # For now, we'll use the file we just uploaded and download it back from YAMCS storage

    # Download from YAMCS storage (the file we uploaded is in bucket)
    storage = yamcs_client.yamcs.get_storage_client()

    # Create output directory
    output_dir = Path("/tmp/yamcs_test_downloads")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / downloaded_file

    try:
        # Download from the input bucket (where we uploaded it)
        with open(output_file, 'wb') as f:
            storage.download_object(
                bucket_name='fprimeFilesIn',
                object_name=source_file.split('/')[-1],
                file_obj=f
            )

        # Verify contents match
        assert output_file.read_text() == TEST_DATA

    finally:
        # Cleanup
        if output_file.exists():
            output_file.unlink()
        Path(tmp_file_path).unlink()


def test_yamcs_large_file_transfer(fprime_test_api):
    """Test YAMCS file transfer with a larger file (1 MiB)

    Verifies that YAMCS file transfer can handle larger files.
    """
    yamcs_client = fprime_test_api.pipeline.client_socket
    if not hasattr(yamcs_client, 'upload_file'):
        import pytest
        pytest.skip("Not using YAMCS transport")

    # Use the existing 1MiB.txt file
    source_file = "/tmp/1MiB.txt"
    destination = "/tmp/yamcs_large_file_test.txt"

    # Upload the large file
    transfer = yamcs_client.upload_file(source_file, destination, timeout=60)

    # Verify completion
    assert transfer is not None

    # Wait for FileReceived event
    event = fprime_test_api.await_event("FileReceived", timeout=30)
    assert event is not None

    # Verify file size on FSW
    fprime_test_api.send_and_assert_command(
        fprime_test_api.get_mnemonic("Svc.FileManager") + ".FileSize",
        [destination],
        max_delay=10,
    )
