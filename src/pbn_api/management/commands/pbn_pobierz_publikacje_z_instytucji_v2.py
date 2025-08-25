from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from tqdm import tqdm

from pbn_api import integrator
from pbn_api.management.commands.util import PBNBaseCommand


def process_single_page_v2(
    client, page_resource, page_num, progress_lock=None, stdout=None, style=None
):
    """
    Process a single page of publications from V2 API.

    Args:
        client: PBN API client
        page_resource: PageableResource instance
        page_num: Page number to fetch and process
        progress_lock: Threading lock for thread-safe output
        stdout: Command stdout for output
        style: Command style for colored output

    Returns:
        dict: Result of processing with success/error information and counts
    """
    result = {
        "page_num": page_num,
        "success": True,
        "error": None,
        "processed_count": 0,
        "success_count": 0,
        "error_count": 0,
        "errors": [],
    }

    try:
        # Fetch the specific page
        page_data = page_resource.fetch_page(page_num)
        result["processed_count"] = len(page_data)

        # Process each publication in the page
        for elem in page_data:
            try:
                integrator.zapisz_publikacje_instytucji_v2(client, elem)
                result["success_count"] += 1
            except Exception as e:
                result["error_count"] += 1
                error_msg = (
                    f"Error processing publication {elem.get('uuid', 'unknown')}: {e}"
                )
                result["errors"].append(error_msg)
                if stdout and style and progress_lock:
                    with progress_lock:
                        tqdm.write(style.ERROR(error_msg))

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        if stdout and style and progress_lock:
            with progress_lock:
                tqdm.write(style.ERROR(f"Error processing page {page_num}: {e}"))

    return result


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--threads",
            type=int,
            default=16,
            help="Number of threads to use for parallel processing (default: 16, max: 32)",
        )
        parser.add_argument(
            "--no-threads",
            action="store_true",
            help="Disable threading for debugging purposes",
        )

    def handle(self, app_id, app_token, base_url, user_token, *args, **kw):
        num_threads = max(1, min(32, kw.get("threads", 16)))  # Clamp between 1 and 32
        no_threads = kw.get("no_threads", False)

        if no_threads:
            num_threads = 1

        client = self.get_client(
            app_id=app_id, app_token=app_token, base_url=base_url, user_token=user_token
        )

        if num_threads > 1:
            tqdm.write(
                self.style.SUCCESS(
                    f"Using {num_threads} threads for parallel processing"
                )
            )
        else:
            tqdm.write(
                self.style.WARNING("Threading disabled - processing sequentially")
            )

        # Get the pageable resource
        page_resource = client.get_institution_publications_v2()
        total_pages = page_resource.total_pages
        total_elements = getattr(page_resource, "total_elements", "unknown")

        if total_pages == 0:
            tqdm.write(self.style.WARNING("No publications found to process"))
            return

        tqdm.write(
            self.style.SUCCESS(
                f"Found {total_elements} publications in {total_pages} pages to process"
            )
        )

        # Initialize progress tracking
        progress_lock = Lock()
        total_success_count = 0
        total_error_count = 0
        total_processed = 0

        if num_threads == 1 or no_threads:
            # Sequential processing for debugging
            for page_num in tqdm(range(total_pages), desc="Processing pages"):
                result = process_single_page_v2(
                    client,
                    page_resource,
                    page_num,
                    progress_lock,
                    self.stdout,
                    self.style,
                )
                total_processed += result["processed_count"]
                total_success_count += result["success_count"]
                total_error_count += result["error_count"]
        else:
            # Parallel processing with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                # Submit all page processing tasks
                future_to_page = {
                    executor.submit(
                        process_single_page_v2,
                        client,
                        page_resource,
                        page_num,
                        progress_lock,
                        self.stdout,
                        self.style,
                    ): page_num
                    for page_num in range(total_pages)
                }

                tasks_submitted = len(future_to_page)
                tqdm.write(
                    self.style.SUCCESS(
                        f"Submitted {tasks_submitted} page processing tasks to {num_threads} worker threads"
                    )
                )

                # Process completed tasks with progress bar
                with tqdm(total=total_pages, desc="Processing pages") as pbar:
                    for future in as_completed(future_to_page):
                        result = future.result()
                        total_processed += result["processed_count"]
                        total_success_count += result["success_count"]
                        total_error_count += result["error_count"]
                        pbar.update(1)

        # Print final summary
        tqdm.write(
            self.style.SUCCESS(
                f"\nCompleted processing {total_processed} publications from {total_pages} pages"
            )
        )
        tqdm.write(self.style.SUCCESS(f"Successful: {total_success_count}"))
        if total_error_count > 0:
            tqdm.write(self.style.ERROR(f"Errors: {total_error_count}"))
