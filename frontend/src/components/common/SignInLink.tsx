import React from 'react';
import { Link, useLocation } from 'react-router-dom';

/**
 * A link to /login that remembers the current page, so signing in returns the person to where
 * they were (SignInPage reads `state.from`).
 */
export const SignInLink: React.FC<{ className?: string; children: React.ReactNode }> = ({ className, children }) => {
  const location = useLocation();
  return (
    <Link to="/login" state={{ from: `${location.pathname}${location.search}` }} className={className}>
      {children}
    </Link>
  );
};
