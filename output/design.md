# Campus Customs Quest Board: Design

The dashboard (`frontend/`, React + Vite + TypeScript) turns the agent team into
a fantasy party. Every ticket is a quest, every agent is a character, the
checking account is a vault of gold, and the human is the **Guild Master**, the
only one who can stamp a payment. The theme is not decoration: each game idea
maps to one real safety rule in the backend.

Look: near-black background, hot-pink accents for the party and glowing action,
gold only for money. Serif headings for the storybook feel, plain sans-serif for
reading. Motion is reduced automatically for people who ask for it.

## Run it

```bash
cd backend && uvicorn main:app --reload --port 8000   # the API
cd frontend && npm install && npm run dev             # http://localhost:5173
```

The front end calls `http://localhost:8000` (change it with `VITE_API_URL`). The
backend allows requests from `http://localhost:5173` only (CORS in
`backend/main.py`), so Vite uses a fixed port and fails loudly if it is taken.

## Character classes

| Character | Real agent | Class | Plays like |
|---|---|---|---|
| 👑 **The Boss** | `boss` | **Main Player** | Leads the party. Reads the quest scroll and decides who acts. |
| 🎒 **Merchant** | `inventory` | NPC | Counts the stockroom, haggles with vendors, scribes restock pleas. |
| 🔮 **Treasury Mage** | `accounting` | NPC | Reads ledgers and margins, prepares payments for the Seal. |
| 🏰 **Castle Steward** | `facilities` | NPC | Keeps the keep: leases and rent dates. |
| 📯 **Town Herald** | `customer_service` | NPC | Writes letters that are never posted (drafts only). |
| 🧙 **Guild Master** | the human | Seal holder | The only one who can spend gold. |

The Boss gets a larger gold-edged card. NPCs sit in a row below. Delegations and
handoffs show as a character speaking **to** another ("Boss ➜ Merchant"), so the
team structure is visible as conversation.

## Quest log mechanics

- **Quest scrolls.** The three tickets are scrolls with a title (for example
  "The Missing Tee"), the requester, and the ticket type. A badge shows
  **Open**, **In Progress**, **Completed** (or **Quest Failed**). A gold "seal
  awaited" chip appears on any scroll with a payment still waiting.
- **Begin Quest.** Pressing it starts the agent team (`POST /tickets/{id}/run`).
  The Boss is the active player; NPCs join as they are called.
- **Live party dialogue.** The board polls the activity route about once a
  second while a quest runs and turns audit events into lines: speech for
  delegations and handoffs, glowing `⚡ spell` lines for tool calls (each tool has
  a flavor verb, for example `request_payment` "prepares a payment for the Guild
  Master's Seal"), dim `↳` lines for what the tool returned, and quoted report
  lines when an agent finishes. Raw tool names stay visible so nothing is hidden.
- **Glowing indicators.** The character currently acting pulses pink and shows
  its latest spell in a glowing chip. Finished characters turn green with
  "Task done · N actions". Waiting characters rest "in the tavern".
- **Victory.** When the run finishes the quest is marked **Completed**
  automatically and a victory banner opens with one summary card per character:
  what they learned, what they did, and what still awaits the Seal. "Completed"
  means the party has done everything it is allowed to do. The ticket in the
  database stays `waiting_approval` until a human has stamped the payments; the
  banner says how many seals are pending.
- **Rewind the Realm.** Resets the database to its original values for a fresh
  run (with a confirmation). The audit trail is kept.

## Gold Vault

The checking balance from `GET /cash` is the **Shop Gold Vault**, shown large in
the header in gold, and it counts up or down when it changes. Under it, a pink
line shows gold already *promised* to unsealed scrolls, so the human sees both
what is in the vault and what is spoken for. Approving a payment updates the
vault immediately from the approval response and flashes it.

## Guild Master Seal (human approval)

Agents can only prepare payments. The header button **🔏 Seals Awaiting (n)**
pulses while anything is waiting and opens the Guild Master's Seal modal:

1. The modal states the rule in plain words: the party can only prepare; gold
   leaves the vault only when you stamp.
2. You must type your name first. The buttons stay locked until you do, and the
   name is stored with the payment as the approver.
3. Each pending scroll shows what it is ("Rent to the Castle", "Vendor invoice
   #501"), the amount, the reason, and **the vault after sealing**, running
   across the list so stacked payments show how little gold is left.
4. **Stamp the Seal** executes the payment. **Deny** rejects it. If the vault
   cannot cover it, the backend refuses and the modal shows the reason.

## UX choices that make oversight feel like play

- **Seals instead of "approve".** A named person stamping a seal is a ceremony
  with a clear owner, and the stored name makes the audit trail personal.
- **The party talks.** Handoffs read as dialogue, so a person can follow who
  asked whom for what without reading JSON.
- **Spells, not logs.** Tool calls glow like spells but keep their real names, so
  the game layer never hides what the agents did.
- **Promised gold.** Showing balance and promises together makes the cash
  conflict between rent and the vendor invoice something you can see.
- **Completed does not mean paid.** The victory card lists what is still
  awaiting the Seal, so a finished quest cannot be mistaken for spent money.
- **No letter leaves the keep.** The Herald's drafts are shown as drafts; there
  is no send button anywhere.
- **Rewind.** A reset that feels like a game mechanic encourages re-running the
  three quests and comparing plans against what happened.
- **Accessible by default.** Real buttons and dialog roles, `aria-live` regions
  for the log and active character, Escape closes the modal, strong contrast,
  and reduced motion is respected.
