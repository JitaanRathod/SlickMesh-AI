import SectionTitle from '../components/section-title';
import { ChartNoAxesCombinedIcon, KeyRoundIcon, SquareDashedMousePointerIcon } from 'lucide-react';

export default function HowItWorksSection() {
    const data = [
        {
            title: 'Sign Up Instantly',
            description: 'Create an account in seconds and no credit card required.',
            icon: KeyRoundIcon,
        },
        {
            title: 'Connect Your Tools',
            description: 'Easily integrate with your apps like Slack, Stripe or Notion.',
            icon: SquareDashedMousePointerIcon,
        },
        {
            title: 'Get Real-Time Insights',
            description: 'Track performance, automate tasks and make decisions',
            icon: ChartNoAxesCombinedIcon,
        },
    ];
    return (
        <section className='flex flex-col items-center justify-center'>
            <SectionTitle title='How It Works' description='SlideX is a powerful AI-powered platform that allows you to create and edit slides effortlessly with AI.' />

            <div className='mt-20 flex flex-wrap items-center justify-center gap-10'>
                {data.map((item, index) => (
                    <div key={index} className='rounded-[14px] bg-gray-200/80 p-0.5 pt-4 transition-all duration-300 hover:-translate-y-1'>
                        <div className='relative flex max-w-80 flex-col items-center rounded-xl bg-white p-6 pb-10'>
                            <div className='absolute -top-6 rounded-full bg-gray-800 p-3'>
                                <item.icon className='size-6 text-white' />
                            </div>
                            <h3 className='mt-10 text-center text-base font-medium'>{item.title}</h3>
                            <p className='mt-6 text-center text-gray-500'>{item.description}</p>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}
