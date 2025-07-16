import { Suspense } from 'react';
import Profile from '../components/Profile';

export default function Dashboard() {
    return (
        <div className="p-8">
            <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
            <Suspense fallback={<div>Loading...</div>}>
                <Profile />
            </Suspense>
        </div>
    )
}