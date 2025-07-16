import { Suspense } from 'react';
import Profile from './Dashboard';

export default function Dashboard() {
    return (
        <div className="p-8">
            <h1 className="text-2xl font-bold mb-6">FindTunes Dashboard</h1>
            <Suspense fallback={<div>Loading...</div>}>
                <Profile />
            </Suspense>
        </div>
    );
};
