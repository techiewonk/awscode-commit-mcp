"""Map botocore ClientError to messages; optional retry for throttling."""

from botocore.exceptions import ClientError


def handle_aws_error(exc: ClientError) -> str:
    """Map ClientError to a short user-facing message."""
    code = (exc.response or {}).get("Error", {}).get("Code", "")
    msg = (exc.response or {}).get("Error", {}).get("Message", str(exc))
    if code == "ThrottlingException":
        return f"Rate limited: {msg}"
    if code == "RepositoryDoesNotExistException":
        return f"Repository not found: {msg}"
    if code == "BranchDoesNotExistException":
        return f"Branch not found: {msg}"
    if code == "CommitIdDoesNotExistException":
        return f"Commit not found: {msg}"
    if code == "FileDoesNotExistException":
        return f"File not found: {msg}"
    if code == "PathDoesNotExistException":
        return f"Path not found: {msg}"
    if code == "InvalidParameterValueException":
        return f"Invalid parameter: {msg}"
    if code == "EncryptionKeyAccessDeniedException":
        return f"Encryption key access denied: {msg}"
    return f"AWS error ({code}): {msg}"
