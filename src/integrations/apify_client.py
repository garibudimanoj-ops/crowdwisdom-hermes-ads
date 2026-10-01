from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from apify_client import ApifyClient


class ApifyIntegrationError(RuntimeError):
    """Raised when an Apify operation fails."""


class ApifyRunner:
    """Wrapper around the Apify Python SDK v3.

    Translates our stable ``run_actor(actor_id, run_input, timeout_secs)``
    interface into the current Apify v3 API:

        run = actor_client.call(
            run_input=run_input,
            wait_duration=timedelta(seconds=timeout_secs),
        )

    The returned object is a typed ``Run`` instance; we read
    ``run.default_dataset_id`` and use the dataset client to fetch items.
    """

    def __init__(self) -> None:
        token = os.getenv("APIFY_API_TOKEN")

        if not token:
            raise ApifyIntegrationError(
                "APIFY_API_TOKEN is missing from the environment."
            )

        self.client = ApifyClient(token)

    def run_actor(
        self,
        actor_id: str,
        run_input: dict[str, Any],
        timeout_secs: int = 300,
    ) -> list[dict[str, Any]]:
        try:
            run = self.client.actor(actor_id).call(
                run_input=run_input,
                wait_duration=timedelta(seconds=timeout_secs),
            )

            if run is None:
                raise ApifyIntegrationError(
                    f"Apify actor '{actor_id}' returned no run object."
                )

            dataset_id = run.default_dataset_id

            if not dataset_id:
                raise ApifyIntegrationError(
                    "Apify actor completed without a dataset."
                )

            items = list(
                self.client.dataset(dataset_id).iterate_items()
            )

            return items

        except ApifyIntegrationError:
            raise
        except Exception as exc:
            raise ApifyIntegrationError(
                f"Apify actor '{actor_id}' failed: {exc}"
            ) from exc