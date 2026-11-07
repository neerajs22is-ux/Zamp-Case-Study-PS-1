import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

interface ScreenPathProps {
  title: string;
  children: React.ReactNode;
  links?: { to: string; label: string }[];
}
/** A short orientation and real navigation, without inventing process progress. */
export const ScreenPath: React.FC<ScreenPathProps> = ({
  title,
  children,
  links = [],
}) => (
  <section className="screen-path" aria-label={title}>
    <div className="screen-path-copy">
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
    {links.length > 0 && (
      <nav aria-label={`${title}: related screens`}>
        {links.map((link) => (
          <Link key={link.to} to={link.to}>
            {link.label}
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        ))}
      </nav>
    )}
  </section>
);
