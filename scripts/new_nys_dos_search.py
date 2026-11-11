
import asyncio
import json
import os
import re
from typing import Literal

from pydantic import BaseModel, Field
from browser_use import Agent, ChatGoogle


NYS_DOS_URL = "https://apps.dos.ny.gov/publicInquiry/"

MAX_ATTEMPTS = 3
MAX_STEPS = 35


# --------------------------------------------------
# Structured output models
# --------------------------------------------------

class NYSDOSRecord(BaseModel):
    company_name: str
    dos_id: str
    entity_type: str
    status: str
    filing_date: str
    search_term: str


class NYSDOSResponse(BaseModel):
    status: Literal["success", "no_results", "partial", "error"]
    search_term: str
    total_results: int
    pages_reviewed: int
    all_pages_reviewed: bool
    notes: str
    page_confirmation: str
    results: list[NYSDOSRecord] = Field(default_factory=list)


# --------------------------------------------------
# Parse the agent's response
# --------------------------------------------------

def parse_agent_result(raw_result):

    if raw_result is None:
        return {
            "status": "error",
            "error": "The agent did not return a structured result.",
            "results": [],
        }

    # Convert a Pydantic model into a dictionary.
    if hasattr(raw_result, "model_dump"):
        data = raw_result.model_dump()

    elif isinstance(raw_result, dict):
        data = raw_result

    else:
        text = str(raw_result).strip()

        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            return {
                "status": "error",
                "error": "The agent did not return valid JSON.",
                "results": [],
                "raw_result": text,
            }

        try:
            data = json.loads(text[start:end + 1])

        except json.JSONDecodeError:
            return {
                "status": "error",
                "error": "Could not read the agent's JSON response.",
                "results": [],
                "raw_result": text,
            }

    if not isinstance(data.get("results"), list):
        return {
            "status": "error",
            "error": "The agent response did not contain a results list.",
            "results": [],
        }

    valid_statuses = ("success", "no_results", "partial", "error")

    if data.get("status") not in valid_statuses:
        return {
            "status": "error",
            "error": "The agent returned an invalid search status.",
            "results": [],
        }

    cleaned_results = []

    for item in data["results"]:

        if not isinstance(item, dict):
            continue

        cleaned_results.append({
            "company_name": item.get("company_name", ""),
            "dos_id": str(item.get("dos_id", "")),
            "entity_type": item.get("entity_type", ""),
            "status": item.get("status", ""),
            "filing_date": item.get("filing_date", ""),
            "search_term": item.get("search_term", ""),
        })

    data["results"] = cleaned_results

    return data


# --------------------------------------------------
# Verify that the agent actually performed the search
# --------------------------------------------------

def verify_search(history, company_name, result):

    actions = [
        action.lower()
        for action in history.action_names()
    ]

    print("Actions performed:", actions)

    # The agent must navigate to the website.
    if "navigate" not in actions:
        return False, "The agent did not navigate to the website."

    # The agent must enter the company name.
    if "input" not in actions:
        return False, "The agent did not enter the company name."

    # The agent must submit the search.
    if not any(action in actions for action in ("click", "send_keys")):
        return False, "The agent did not submit the search."

    # The agent must extract information from the results page.
    if "extract" not in actions:
        return False, "The agent did not extract information from the results page."

    # Confirm that the exact company name appeared in an input action.
    model_actions = history.model_actions()

    action_text = json.dumps(model_actions, default=str).lower()

    if company_name.lower() not in action_text:
        return False, "The exact company name could not be verified in the browser actions."

    # Verify the returned search term.
    if result.get("search_term", "").strip().lower() != company_name.lower():
        return False, "The returned search term did not match the requested company."

    # A no-results response must include visible website confirmation.
    if result["status"] == "no_results":

        if result.get("total_results") != 0:
            return False, "The agent reported no results, but the result count was not zero."

        if not result.get("page_confirmation", "").strip():
            return False, "The agent did not provide the website's no-results confirmation."

    # A successful search must contain actual records.
    elif result["status"] == "success":

        if not result["results"]:
            return False, "The agent reported success without returning any records."

        if not result.get("all_pages_reviewed"):
            return False, "The agent reported success without confirming all pages were reviewed."

    elif result["status"] == "partial":

        if not result["results"]:
            return False, "The agent reported partial results but returned no records."

    elif result["status"] == "error":

        return False, result.get("notes") or "The website search could not be completed."

    # Make sure records contain identifying information.
    for record in result["results"]:

        if not record["company_name"] or not record["dos_id"]:
            return False, "A returned record is missing its company name or DOS ID."

    # Do not claim complete success if the returned records
    # do not account for the website's reported result count.
    if (
        result["status"] == "success"
        and result["total_results"] > len(result["results"])
    ):
        result["status"] = "partial"
        result["all_pages_reviewed"] = False
        result["notes"] = (
            result.get("notes", "")
            + " Not all reported records were included in the extracted results."
        ).strip()

    return True, None


# --------------------------------------------------
# Main asynchronous search function
# --------------------------------------------------

async def search_nys_dos_async(company_name):

    company_name = company_name.strip()

    if not company_name:
        return {
            "status": "error",
            "error": "No company name was provided.",
            "results": [],
        }

    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "GOOGLE_API_KEY is missing. Set it in Terminal first."
        )

    task = f"""
    Visit the official NYS Department of State Public Inquiry website:

    {NYS_DOS_URL}

    Search for this exact company name:

    {company_name}

    IMPORTANT:
    You must actually interact with the website.
    Do not guess, assume, or invent search results.

    SEARCH INSTRUCTIONS:

    1. Navigate to the official website.
    2. Inspect the page and wait for the search form to load.
    3. If the page is blank, wait 3 seconds and inspect it again.
    4. If the page is still blank, stop and return status "error".
       Do not repeatedly reload the same blank page.
    5. Select all four entity types:
       - Corporation
       - Limited Liability Company
       - Limited Partnership
       - Limited Liability Partnership
    6. Enter the exact company name provided above.
    7. Use the website's partial-name search.
    8. Do NOT shorten the name, remove legal suffixes,
       try alternative spellings, or run additional searches.
    9. Click the actual Search button to submit the form.
    10. Wait for the results page to load.
    11. Verify that the results page actually appeared.
    12. Use the extract action to read the results page.
    13. Collect the matching records and their details.
    14. If possible, select the option to display all results
        on one page.
    15. Otherwise, review each results page using pagination.
    16. Do not claim that pages were reviewed unless you
        actually inspected them.

    DO NOT CALL DONE OR FINISH THE TASK BEFORE:
    - The search form was completed.
    - The search was submitted.
    - The results page was inspected.
    - The available matching records were extracted.

    FOR EACH RESULT, COLLECT:

    - company_name: Exact legal business name
    - dos_id: DOS ID
    - entity_type: Entity type
    - status: Current displayed status
    - filing_date: Date of first filing
    - search_term: The exact search term used

    ALSO COLLECT:

    - total_results: Total number reported by the website
    - pages_reviewed: Number of pages actually reviewed
    - all_pages_reviewed: True only if every available result was reviewed
    - notes: Explain limitations or incomplete results
    - page_confirmation: Exact visible text confirming the results
      page loaded. For no results, quote the website's no-results message.

    STATUS RULES:

    - success: Records were found and all results were reviewed.
    - no_results: The website explicitly displayed zero matching records.
    - partial: Records were found but not all results could be reviewed.
    - error: The website failed to load, the search could not be submitted,
      or the results page could not be accessed.

    Never report no_results because a page was blank or a search failed.

    Never invent company records, DOS IDs, filing dates, or page counts.

    Return the final result using the required structured output schema.
    """

    last_error = "Search did not complete."

    for attempt in range(1, MAX_ATTEMPTS + 1):

        print(f"\\nNYS DOS search attempt {attempt}/{MAX_ATTEMPTS}")

        try:

            agent = Agent(
                task=task,
                llm=ChatGoogle(model="gemini-3.5-flash-lite"),
                output_model_schema=NYSDOSResponse,
                use_judge=False,
            )

            history = await asyncio.wait_for(
                agent.run(max_steps=MAX_STEPS),
                timeout=240,
            )

            # Do not accept plain-English final responses.
            structured_result = history.structured_output

            if structured_result is None:
                last_error = (
                    "The agent did not return the required structured output."
                )

            else:

                result = parse_agent_result(structured_result)

                # Verify actual browser actions and returned records.
                valid, verification_error = verify_search(
                    history,
                    company_name,
                    result,
                )

                if valid:
                    return result

                last_error = verification_error

        except asyncio.TimeoutError:

            last_error = "The browser search timed out after 240 seconds."

        except Exception as e:

            last_error = str(e)

        print(f"Attempt {attempt} failed: {last_error}")

        if attempt < MAX_ATTEMPTS:
            wait_time = attempt * 5
            print(f"Waiting {wait_time} seconds before retrying...")
            await asyncio.sleep(wait_time)

    return {
        "status": "error",
        "error": f"Search failed after {MAX_ATTEMPTS} attempts: {last_error}",
        "results": [],
    }


# --------------------------------------------------
# Synchronous function for the Streamlit application
# --------------------------------------------------

def search_nys_dos(company_name):

    try:
        asyncio.get_running_loop()

    except RuntimeError:
        return asyncio.run(search_nys_dos_async(company_name))

    raise RuntimeError(
        "An event loop is already running. "
        "Use await search_nys_dos_async(company_name) instead."
    )


# --------------------------------------------------
# Run this file independently from Terminal
# --------------------------------------------------

if __name__ == "__main__":

    vendor = input("Enter the business name to search: ").strip()

    if vendor:

        result = search_nys_dos(vendor)

        print("\\n--- NYS DOS SEARCH RESULTS ---\\n")
        print(json.dumps(result, indent=4))

    else:
        print("No business name entered.")

