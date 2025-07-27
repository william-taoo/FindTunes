import { Suspense } from 'react';
import Dashboard from './Dashboard';

export default function Page() {
    return (
        <div className="p-8">
            <h1 className="text-2xl font-bold mb-6">FindTunes Dashboard</h1>
            <Suspense fallback={<div>Loading...</div>}>
                <Dashboard />
            </Suspense>
        </div>
    );
};
