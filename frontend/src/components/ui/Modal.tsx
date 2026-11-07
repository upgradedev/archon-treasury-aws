import React, {useRef} from 'react';
import {useOutsideClick} from '../../hooks/useOutsideClick';
export const Modal: React.FC<{open:boolean;title:string;onClose:()=>void;children:React.ReactNode}>=({open,title,onClose,children})=>{
 const dialogRef=useRef<HTMLDivElement>(null);useOutsideClick(dialogRef,()=>{if(open)onClose();});if(!open)return null;
 return <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-overlay" role="dialog" aria-modal="true" aria-label={title}><div ref={dialogRef} className="w-full max-w-xl bg-surface border border-border rounded-md overflow-hidden">{children}</div></div>;
};
