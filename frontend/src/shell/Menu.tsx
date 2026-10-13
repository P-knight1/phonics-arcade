import { Link } from "react-router-dom";
import { usePlayer } from "./session";

const ITEMS = [
  { to: "/games/word-flash", title: "Word Flash", text: "Read the word before it hides." },
  { to: "/games/sound-surgery", title: "Sound Surgery", text: "Take a sound out, or swap it." },
  { to: "/games/echo-chain", title: "Echo Chain", text: "Repeat a growing chain of sounds." },
  { to: "/games/story-recall", title: "Story Recall", text: "Read a story made for you." },
  { to: "/progress", title: "Progress", text: "See how you are doing." },
];

export default function Menu() {
  const player = usePlayer();
  return (
    <>
      <h1>Hi {player.name}</h1>
      <p className="lead">Pick a game.</p>
      <nav className="menu">
        {ITEMS.map((item) => (
          <Link key={item.to} to={item.to} className="menu-item">
            <span className="menu-title">{item.title}</span>
            <span>{item.text}</span>
          </Link>
        ))}
      </nav>
    </>
  );
}
