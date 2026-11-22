import { Link } from "react-router-dom";
import { displayName, useSession } from "./session";

// Each activity has its own colour and picture, so a child finds it again without reading the title.
const ITEMS = [
  { to: "/games/word-flash", icon: "⚡", tone: "sun", title: "الكلمة الخاطفة", text: "اقرأ الكلمة قبل أن تختفي." },
  { to: "/games/sound-surgery", icon: "✂️", tone: "sea", title: "جراحة الأصوات", text: "احذف صوتًا من الكلمة أو بدّله." },
  { to: "/games/rhythmic-reading", icon: "🥁", tone: "rose", title: "القراءة على الإيقاع", text: "اقرأ الكلمات مع الإيقاع دون توقف." },
  { to: "/games/story-recall", icon: "📖", tone: "leaf", title: "قصتي", text: "اقرأ قصة كُتبت لك." },
  { to: "/progress", icon: "📈", tone: "sky", title: "تقدّمي", text: "شاهد كيف تتحسّن." },
];

export default function Menu() {
  const session = useSession();
  const name = session.status === "in" ? displayName(session.player, session.guest) : "";
  return (
    <>
      <h1>أهلًا {name}</h1>
      <p className="lead">ماذا نتدرّب اليوم؟</p>
      <nav className="menu">
        {ITEMS.map((item) => (
          <Link key={item.to} to={item.to} className={`menu-item tone-${item.tone}`}>
            <span className="menu-icon" aria-hidden="true">
              {item.icon}
            </span>
            <span>
              <span className="menu-title">{item.title}</span>
              <span className="menu-text">{item.text}</span>
            </span>
          </Link>
        ))}
      </nav>
    </>
  );
}
