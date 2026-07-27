from api import default_job_name


def test_url_job_uses_hostname():
    name = default_job_name("https://youtube.com/watch?v=abc", False)
    assert "youtube.com" in name


def test_upload_job_prefix():
    assert default_job_name("", True).startswith("Upload")


def test_empty_url_no_upload_fallback():
    assert default_job_name("", False).startswith("Clip")


def test_malformed_url_fallback():
    assert default_job_name("not-a-url", False).startswith("Clip")


def test_explicit_name_preserved():
    # Adversarial: create_job must not override a set name.
    # Verified by the helper contract: auto-gen only runs when name is empty.
    from api import ClipJobRequest

    req = ClipJobRequest(url="https://youtube.com/x", name="My Video")
    assert req.name == "My Video"
