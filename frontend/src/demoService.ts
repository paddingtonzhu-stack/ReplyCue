export type Intention =
  | "Reconnect"
  | "Make plans"
  | "Keep it friendly"
  | "Set a boundary";
const replies: Record<Intention, string[][]> = {
  Reconnect: [
    [
      "Hey! I've been good — how about you?",
      "Hey you :) How's the new job going?",
      "Hey! Still up for that coffee sometime?",
    ],
    [
      "Maya! Good to hear from you. How have you been?",
      "Hey :) It's been a busy few weeks. How's everything?",
      "I was just thinking about that dinner! How are you?",
    ],
  ],
  "Make plans": [
    [
      "Hey! I'm good. Want to catch up over coffee this weekend?",
      "Good to hear from you :) Are you free for a walk on Sunday?",
      "We never did plan that coffee. How does Saturday sound?",
    ],
    [
      "Hey Maya! Fancy a coffee next week?",
      "Would love to catch up. What does your weekend look like?",
      "Still thinking about that little café — want to try it together?",
    ],
  ],
  "Keep it friendly": [
    [
      "Hey! Doing well, thanks. Hope you've been good too!",
      "Hey Maya! How's life treating you?",
      "Nice to hear from you! What have you been up to?",
    ],
    [
      "Hey! All good here. How are things with you?",
      "Hi Maya :) Hope the new job is going well.",
      "Good to hear from you! Been keeping busy?",
    ],
  ],
  "Set a boundary": [
    [
      "Hey, thanks for reaching out. I'm taking some time for myself right now.",
      "Hi Maya. I'm happy to catch up, but I'd like to keep things friendly.",
      "Hey. I'm not looking to reconnect right now, but I wish you well.",
    ],
    [
      "Thanks for checking in. I need a little space at the moment.",
      "Hey Maya. I'd prefer to keep things as friends.",
      "I appreciate the message. I'm focusing on myself for now.",
    ],
  ],
};
// Replace this adapter with a FastAPI request later; no model or personal data is used.
export async function generateReplies(
  intention: Intention,
  variation: number,
): Promise<string[]> {
  await new Promise((resolve) => setTimeout(resolve, 350));
  return replies[intention][variation % replies[intention].length];
}
export const initialReplies = replies.Reconnect[0];
export const memories = [
  {
    fact: "Coffee plans were left open.",
    source: "Mar 2 · Maya: “We should try that little café sometime.”",
  },
  {
    fact: "Maya mentioned starting a new job.",
    source: "Feb 25 · Maya: “First day at the new job on Monday!”",
  },
  {
    fact: "You both enjoyed your last dinner.",
    source: "Mar 2 · You: “That dinner was so much fun!”",
  },
];
