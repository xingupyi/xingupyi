"""Yes / No polls for a GitHub profile README.

Each README button opens a pre-filled issue titled "[Vote] <question-id> yes|no".
When the issue is submitted, this script records the vote in polls.json
(one vote per GitHub user per question; voting again changes your vote)
and redraws the block between <!-- POLLS:START --> and <!-- POLLS:END --> in README.md.

To add or change questions, edit polls.json, then run the workflow manually.
"""
import json
import os
import re
from urllib.parse import quote

README = "README.md"
DATA = "polls.json"
START, END = "<!-- POLLS:START -->", "<!-- POLLS:END -->"
RESULT_FILE = "vote_result.md"   # message the workflow posts back on the issue
BAR = 10                         # bar length in blocks

ISSUE_BODY = (
    "Just click **Create** / **Submit new issue** below to cast your vote! 🗳️\n\n"
    "_Changed your mind? Vote again any time and your latest vote counts._"
)


def load() -> dict:
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict) -> None:
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def tally(q: dict) -> tuple[int, int]:
    yes = sum(1 for v in q["votes"].values() if v == "yes")
    no = sum(1 for v in q["votes"].values() if v == "no")
    return yes, no


def bar(yes: int, no: int) -> str:
    total = yes + no
    if total == 0:
        return "<code>" + "░" * BAR + "</code> no votes yet"
    filled = round(BAR * yes / total)
    pct = round(100 * yes / total)
    return f"<code>{'█' * filled}{'░' * (BAR - filled)}</code> {pct}% yes"


def vote_link(repo: str, qid: str, choice: str) -> str:
    title = quote(f"[Vote] {qid} {choice}")
    body = quote(ISSUE_BODY)
    return f"https://github.com/{repo}/issues/new?title={title}&body={body}"


def render(data: dict) -> str:
    repo = data["repo"]
    rows = []
    for q in data["questions"]:
        yes, no = tally(q)
        rows.append(
            "<tr>"
            f"<td>{q.get('emoji', '')} {q['text']}</td>"
            f'<td align="center"><a href="{vote_link(repo, q["id"], "yes")}">👍 Yes</a>'
            f' &nbsp; <a href="{vote_link(repo, q["id"], "no")}">👎 No</a></td>'
            f"<td>{bar(yes, no)}<br><sub>👍 {yes} · 👎 {no}</sub></td>"
            "</tr>"
        )
    voters = {login for q in data["questions"] for login in q["votes"]}
    head = '<tr><th align="left">Question</th><th>Vote</th><th align="left">Results</th></tr>'
    foot = f"<sub>{len(voters)} {'person has' if len(voters) == 1 else 'people have'} voted · one vote per question, vote again to change it</sub>"
    return f"{START}\n<table>\n{head}\n" + "\n".join(rows) + f"\n</table>\n{foot}\n{END}"


def apply_vote(data: dict) -> str | None:
    """Record the vote from the issue event. Returns a reply message, or None if no event."""
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        issue = json.load(f).get("issue")
    if not issue:
        return None
    login = issue["user"]["login"]
    m = re.match(r"^\[Vote\]\s+([\w-]+)\s+(yes|no)\s*$", issue["title"].strip(), re.I)
    if not m:
        return f"Hmm, I couldn't read that vote, @{login}. Please use the 👍 / 👎 buttons on my profile."
    qid, choice = m.group(1).lower(), m.group(2).lower()
    q = next((q for q in data["questions"] if q["id"] == qid), None)
    if q is None:
        return f"That question doesn't exist any more, @{login}. Try the buttons on my profile!"
    previous = q["votes"].get(login)
    q["votes"][login] = choice
    yes, no = tally(q)
    verb = "changed your vote to" if previous and previous != choice else "voted"
    emoji = "👍" if choice == "yes" else "👎"
    return (
        f"Thanks @{login}! You {verb} {emoji} **{choice}** on _{q['text']}_\n\n"
        f"Current results: 👍 {yes} · 👎 {no}\n\n"
        f"See all the polls on [my profile](https://github.com/{data['repo'].split('/')[0]}) 🐱"
    )


def main() -> None:
    data = load()
    reply = apply_vote(data)
    if reply is not None:
        save(data)
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            f.write(reply)

    with open(README, encoding="utf-8") as f:
        readme = f.read()
    if START not in readme or END not in readme:
        raise SystemExit(f"README is missing {START} / {END} markers")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    new = pattern.sub(lambda _: render(data), readme)
    if new != readme:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new)
        print("README updated")
    else:
        print("No change")


if __name__ == "__main__":
    main()
