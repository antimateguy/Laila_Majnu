"""Word and line pools for synthetic chats. All text is invented for tests."""

SELF_NAMES = ["Aarav Sharma", "Kabir Mehta", "Ishaan Rao", "Meera Iyer", "Zoya Khan", "Tara Joshi"]
OTHER_NAMES = ["Riya 🌸", "Ananya Verma", "Vihaan Gupta", "Sana Qureshi", "Dev Malhotra", "Noor Ali"]
THIRD_PARTY_NAMES = ["Priya", "Rohan", "Neha", "Arjun", "Pooja", "Siddharth", "Kavya", "Aditya"]

ENGLISH = {
    "greeting": ["hey", "hi!", "good morning", "heyyy", "you up?", "hello stranger"],
    "question": [
        "what are you doing today?",
        "did you eat?",
        "how was the exam?",
        "are you free this weekend?",
        "which movie should we watch?",
        "how's your mom now?",
        "did you reach home?",
    ],
    "answer": [
        "just reached home",
        "nothing much, scrolling reels",
        "it went okay I think",
        "maybe, let me check",
        "the one with the long trailer",
        "she is better now, thanks for asking",
        "yes, ate already",
    ],
    "affection": ["miss you", "love talking to you", "you're the best ❤️", "sending you a hug 😘"],
    "laugh": ["hahaha", "lol", "😂😂", "haha stop", "🤣"],
    "filler": ["ok", "k", "hmm", "lol", "okay"],
    "we": ["we should go there sometime", "let's plan our trip", "us two against the world"],
    "conflict": ["sorry, my bad", "why didn't you reply?", "whatever", "fine."],
    "plain": [
        "the traffic today was insane",
        "my manager scheduled another meeting",
        "it's raining here",
        "listening to old songs tonight",
        "I finally finished that book",
        "the canteen chai is getting worse",
    ],
}

HINGLISH = {
    "greeting": ["heyy", "uth gaye?", "kya haal hai", "good morning ji", "suno"],
    "question": [
        "aaj kya plan hai?",
        "khana khaya?",
        "exam kaisa gaya?",
        "weekend pe free ho?",
        "kaunsi movie dekhein?",
        "ghar pahunch gaye?",
        "kal milte hain kya?",
    ],
    "answer": [
        "haan abhi pahuncha",
        "kuch nahi bas reels dekh raha",
        "theek tha yaar",
        "dekhte hain, bataunga",
        "nahi abhi tak nahi",
        "haan kha liya",
    ],
    "affection": ["miss kar raha hoon", "tum bahut special ho ❤️", "jaan 😘", "bahut yaad aa rahi hai"],
    "laugh": ["hahaha pagal", "lol", "😂😂😂", "hasna band karo", "🤣"],
    "filler": ["haan", "acha", "hmm", "ok", "theek"],
    "we": ["hum dono chalenge pakka", "hamara plan fix hai", "hum log kab milenge?"],
    "conflict": ["sorry yaar", "reply kyun nahi kiya?", "maaf karo", "whatever", "fine."],
    "plain": [
        "aaj traffic bahut tha",
        "boss ne phir meeting rakh di",
        "yahan baarish ho rahi hai",
        "chai peene ja raha hoon",
        "kal se gym shuru",
        "mummy ne aaj rajma banaya",
    ],
}

EMOJIS = ["😂", "❤️", "🥺", "😅", "🙈", "✨", "😘", "👍", "🔥"]
