import React from 'react';
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {variant?: 'primary'|'secondary'|'ghost';size?: 'sm'|'md';}
export const Button: React.FC<ButtonProps> = ({variant='secondary',size='md',className='',children,...rest}) => {
 const base='inline-flex items-center justify-center font-semibold rounded-sm border transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50';
 const variants={primary:'bg-primary text-primary-foreground border-primary hover:bg-primary',secondary:'bg-surface text-foreground border-border hover:bg-surface-2',ghost:'bg-transparent text-muted border-transparent hover:bg-surface-2'};
 const sizes={sm:'px-2.5 py-1 text-xs',md:'px-3 py-1.5 text-sm'};
 return <button type="button" className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>{children}</button>;
};
