import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  className = '',
  children,
  ...rest
}) => {
  const base =
    'inline-flex items-center justify-center font-semibold rounded-sm border transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50';
  const variants = {
    primary: 'bg-indigo-700 text-white border-indigo-700 hover:bg-indigo-800',
    secondary: 'bg-white text-slate-900 border-slate-300 hover:bg-slate-100',
    ghost: 'bg-transparent text-slate-600 border-transparent hover:bg-slate-100',
  };
  const sizes = {
    sm: 'px-2.5 py-1 text-xs',
    md: 'px-3 py-1.5 text-sm',
  };

  return (
    <button
      type="button"
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
};
