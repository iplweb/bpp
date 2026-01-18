"""Publication fee import utilities"""

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

from .base import ImportStepBase

# Batch size for API calls - balance between API efficiency and memory usage
BATCH_SIZE = 100


class FeeImporter(ImportStepBase):
    """Import publication fees from PBN"""

    step_name = "fee_import"
    step_description = "Import opłat za publikacje"

    def run(self):
        """Import publication fees using batch API calls for better performance."""
        processed = 0
        failed = 0
        api_calls = 0

        for klass_idx, klass in enumerate([Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]):
            klass_name = klass.__name__
            records = list(klass.objects.exclude(pbn_uid_id=None))
            total = len(records)

            self.log("info", f"Processing fees for {total} {klass_name} records")

            if total == 0:
                continue

            # Process in batches
            for batch_start in range(0, total, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total)
                batch_records = records[batch_start:batch_end]

                # Update main progress
                current_progress = (klass_idx * 50) + int((batch_start / total) * 50)
                self.update_progress(
                    current_progress, 100, f"Przetwarzanie {klass_name}"
                )

                # Update subtask progress
                self.update_subtask_progress(
                    batch_start + 1,
                    total,
                    f"Pobieranie opłat {klass_name}: {batch_start + 1}-{batch_end}/{total}",
                )

                # Get batch of publication IDs
                batch_ids = [r.pbn_uid_id for r in batch_records]

                try:
                    # Single API call for entire batch
                    fees_map = self.client.get_publication_fees_batch(batch_ids)
                    api_calls += 1

                    # Process results
                    for rekord in batch_records:
                        fee_result = fees_map.get(str(rekord.pbn_uid_id))

                        if fee_result is not None and "fee" in fee_result:
                            fee_data = fee_result["fee"]
                            rekord.opl_pub_cost_free = fee_data.get(
                                "costFreePublication", False
                            )
                            rekord.opl_pub_research_potential = fee_data.get(
                                "researchPotentialFinancialResources", 0
                            )
                            rekord.opl_pub_research_or_development_projects = (
                                fee_data.get(
                                    "researchOrDevelopmentProjectsFinancialResources",
                                    0,
                                )
                            )
                            rekord.opl_pub_other = fee_data.get("other", 0)
                            rekord.opl_pub_amount = fee_data.get("amount", 0)

                            rekord.save(
                                update_fields=[
                                    "opl_pub_cost_free",
                                    "opl_pub_research_potential",
                                    "opl_pub_research_or_development_projects",
                                    "opl_pub_other",
                                    "opl_pub_amount",
                                ]
                            )
                            processed += 1

                except Exception as e:
                    failed += len(batch_records)
                    self.handle_error(
                        e,
                        f"Nie udało się pobrać opłat dla batcha {klass_name} "
                        f"({batch_start + 1}-{batch_end})",
                    )

        # Clear subtask progress after processing all fees
        self.clear_subtask_progress()
        self.update_progress(100, 100, "Zakończono import opłat")

        self.log(
            "info",
            f"Processed {processed} fees, {failed} failed, {api_calls} API calls "
            f"(batch size: {BATCH_SIZE})",
        )

        # Update statistics
        if hasattr(self.session, "statistics"):
            stats = self.session.statistics
            stats.total_api_calls += api_calls
            stats.save()

        return {
            "fees_imported": processed,
            "fees_failed": failed,
            "api_calls": api_calls,
            "error_count": len(self.errors),
        }
