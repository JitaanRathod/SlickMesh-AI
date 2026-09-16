import { ArrowRightIcon } from 'lucide-react';
import SectionTitle from '../components/section-title';

export default function CallToActionSection() {
    return (
        <section className='flex flex-col items-center justify-center py-20'>
            <SectionTitle title='Try PrebuiltUI for Free' description='PrebuiltUI is a powerful platform that provides ready-to-use, customizable UI components and templates.' />
            <a href='https://prebuiltui.com?utm_source=slidex' className='mt-4 flex items-center gap-2 rounded-full bg-gray-900 px-8 py-2.5 font-medium text-white transition hover:opacity-90'>
                Try now
                <ArrowRightIcon className='size-5' />
            </a>
        </section>
    );
}
