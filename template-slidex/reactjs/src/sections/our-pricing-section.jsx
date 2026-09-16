import SectionTitle from '../components/section-title';
import { CheckIcon } from 'lucide-react';

export default function OurPricingSection() {
    const data = [
        {
            title: 'Starter Plan',
            description: 'Perfect for small business and personal use',
            price: '$19',
            buttonText: 'Get Started',
            features: ['Create up to 10 free projects', 'Get 10 AI tasks monthly', 'Generate simple AI text content', 'Access a basic chatbot tool', 'Receive email-based support only'],
        },
        {
            title: 'Pro Plan',
            description: 'Perfect for medium business and personal use',
            price: '$49',
            mostPopular: true,
            buttonText: 'Upgrade Now',
            features: ['Enjoy unlimited AI task usage', 'Integrate API for smooth workflow', 'Create text and image outputs', 'Get priority chat and email help', 'View detailed analytics and reports'],
        },
        {
            title: 'Custom Plan',
            description: 'Perfect for organizations and personal use',
            price: '$149',
            buttonText: 'Contact Sales',
            features: ['Build fully customized AI models', 'Manage teams with shared access', 'Get a dedicated account manager', 'Integrate private APIs securely', 'Guaranteed uptime with SLA support'],
        },
    ];

    return (
        <section id='pricing' className='flex flex-col items-center justify-center'>
            <SectionTitle title='Our Pricing Plan' description='Our pricing plans are affordable and flexible, catering to all budgets. Choose the plan that suits your needs best.' />
            <div className='mt-12 flex flex-wrap items-center justify-center gap-6'>
                {data.map((item, index) => (
                    <div key={index} className='group w-full max-w-80'>
                        <div className={`flex flex-col items-center justify-center rounded-xl border border-slate-200 p-6 text-center transition-all duration-300 group-hover:-translate-y-1 ${item.mostPopular ? 'bg-gray-800 text-white' : 'bg-white'}`}>
                            <h3 className='text-lg font-semibold'>{item.title}</h3>
                            <p className={item.mostPopular ? 'text-gray-400' : 'text-gray-500'}>{item.description}</p>
                            <p className='mt-4 text-2xl font-semibold'>
                                {item.price} <span className={`text-sm font-normal ${item.mostPopular ? 'text-gray-400' : 'text-gray-500'}`}>/month</span>
                            </p>
                            <button className={`mt-4 w-full rounded-lg bg-gray-100 py-2.5 font-medium text-gray-800 transition ${item.mostPopular ? 'hover:opacity-90' : 'hover:bg-gray-200/70'}`}>{item.buttonText}</button>
                        </div>
                        <div className='mt-2 flex flex-col'>
                            {item.features.map((feature, index) => (
                                <div key={index} className='flex items-center gap-2 border-b border-gray-200 py-2.5 text-gray-800'>
                                    <div className='rounded-full bg-gray-800 p-1'>
                                        <CheckIcon className='size-3 text-white' strokeWidth={2.5} />
                                    </div>
                                    {feature}
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}
