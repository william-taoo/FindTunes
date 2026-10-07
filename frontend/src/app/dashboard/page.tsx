import { Suspense } from 'react';
import Dashboard from './Dashboard';

export default function Page() {
    return (
        <div>
            <Suspense fallback={<div>Loading...</div>}>
                <Dashboard />
            </Suspense>
        </div>
    );
};
