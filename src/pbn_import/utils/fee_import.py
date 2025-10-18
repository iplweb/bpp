"""Publication fee import utilities"""

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

from .base import ImportStepBase


class FeeImporter(ImportStepBase):
    """Import publication fees from PBN"""

    step_name = "fee_import"
    step_description = "Import opłat za publikacje"

    def run(self):
        """Import publication fees"""
        processed = 0
        failed = 0

        for klass_idx, klass in enumerate([Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]):
            klass_name = klass.__name__
            records = klass.objects.exclude(pbn_uid_id=None)
            total = records.count()

            self.log("info", f"Processing fees for {total} {klass_name} records")

            for idx, rekord in enumerate(records):
                # Update main progress
                current_progress = (
                    (klass_idx * 50) + int((idx / total) * 50) if total > 0 else 0
                )
                self.update_progress(
                    current_progress, 100, f"Przetwarzanie {klass_name}"
                )

                # Update subtask progress
                if idx % 10 == 0:  # Update every 10 items to reduce DB load
                    self.update_subtask_progress(
                        idx + 1,
                        total,
                        f"Pobieranie opłat {klass_name}: {idx+1}/{total}",
                    )

                try:
                    res = self.client.get_publication_fee(rekord.pbn_uid_id)

                    if res is not None and "fee" in res:
                        fee_data = res["fee"]
                        rekord.opl_pub_cost_free = fee_data.get(
                            "costFreePublication", False
                        )
                        rekord.opl_pub_research_potential = fee_data.get(
                            "researchPotentialFinancialResources", 0
                        )
                        rekord.opl_pub_research_or_development_projects = fee_data.get(
                            "researchOrDevelopmentProjectsFinancialResources", 0
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
                    failed += 1
                    self.handle_error(
                        e,
                        f"Nie udało się zaimportować opłaty dla {klass_name} {rekord.pbn_uid_id}",
                    )

        # Clear subtask progress after processing all fees
        self.clear_subtask_progress()
        self.update_progress(100, 100, "Zakończono import opłat")

        self.log("info", f"Processed {processed} fees, {failed} failed")

        # Update statistics
        if hasattr(self.session, "statistics"):
            stats = self.session.statistics
            stats.total_api_calls += processed + failed
            stats.save()

        return {
            "fees_imported": processed,
            "fees_failed": failed,
            "error_count": len(self.errors),
        }
