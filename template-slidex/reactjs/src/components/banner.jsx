import { ArrowRightIcon } from 'lucide-react';

export default function Banner() {
    return (
        <div className="flex w-full flex-wrap items-center justify-center bg-gradient-to-b from-orange-500 to-orange-600 py-2 text-center font-medium text-white">
            <p>Templates are live on PrebuiltUI!</p>
            <a href="https://prebuiltui.com" className="ml-3 flex items-center gap-1 rounded-md bg-white px-3 py-1 text-xs text-orange-600 transition hover:bg-slate-200 active:scale-95">
                Check it out
                <ArrowRightIcon className="size-3.5" />
            </a>
        </div>
    );
}
