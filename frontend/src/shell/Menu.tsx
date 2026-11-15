import { Link } from "react-router-dom";
import { displayName, useSession } from "./session";

const ITEMS = [
  { to: "/games/word-flash", title: "الكلمة الخاطفة", text: "اقرأ الكلمة قبل أن تختفي." },
  { to: "/games/sound-surgery", title: "جراحة الأصوات", text: "احذف صوتًا من الكلمة أو بدّله." },
  { to: "/games/story-recall", title: "قصتي", text: "اقرأ قصة كُتبت لك." },
  { to: "/progress", title: "تقدّمي", text: "شاهد كيف تتحسّن." },
];

export default function Menu() {
  const session = useSession();
  const name = session.status === "in" ? displayName(session.player, session.guest) : "";
  return (
    <>
      <h1>أهلًا {name}</h1>
      <p className="lead">اختر لعبة.</p>
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
