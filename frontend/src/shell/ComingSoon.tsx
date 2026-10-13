import { Link } from "react-router-dom";

export default function ComingSoon({ title }: { title: string }) {
  return (
    <>
      <h1>{title}</h1>
      <p className="lead">This one is coming soon.</p>
      <Link to="/" className="button secondary">
        Back to games
      </Link>
    </>
  );
}
