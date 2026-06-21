"""Main entry point for okf_converter."""

from okf_converter.config import settings
from okf_converter.log import get_logger
from okf_converter.utils import get_package_dir


def main() -> None:
    """Run the application."""
    log_path = get_package_dir("log")

    logger = get_logger(
        name="okf_converter",
        log_level=settings.log_level,
        log_file=log_path / "app.log",
    )

    logger.info("Starting okf_converter (env=%s)", settings.app_env)

    # TODO: ajouter la logique applicative ici


if __name__ == "__main__":
    main()
