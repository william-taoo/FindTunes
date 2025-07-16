import { User } from '../Dashboard';

interface ProfileCardProps {
    user: User;
}

const ProfileCard = ({ user }: ProfileCardProps ) => {
    return (
        <div className="bg-gradient-to-br from-spotify-dark to-spotify-darker p-6 rounded-lg shadow-lg w-full md:w-1/3">
            <div className="flex flex-col items-center">
                <img 
                    src={user.profile_image_url || 'no-picture.png'} 
                    alt={user.display_name}
                    className="w-32 h-32 rounded-full object-cover mb-4"
                />
                <h1 className="text-2xl font-bold text-white text-center">{user.display_name}</h1>
                <p className="text-spotify-light text-center">{user.email}</p>
                <p className="text-spotify-light text-center">Listening from: {user.country}</p>
                
                <div className="mt-1 grid grid-cols-2 gap-4 w-full">
                    <div className="bg-spotify-black p-3 rounded-lg">
                        <p className="text-sm text-spotify-light text-center">Followers</p>
                        <p className="font-bold text-white text-center">{user.followers_count}</p>
                    </div>
                    <div className="bg-spotify-black p-3 rounded-lg">
                        <p className="text-sm text-spotify-light text-center">Subscription</p>
                        <p className="font-bold text-white text-center capitalize">{user.product}</p>
                    </div>
                </div>

                <a 
                    href={user.spotify_profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 px-6 py-2 bg-green-500 text-black rounded-full font-medium hover:bg-green-400 transition text-center inline-block"
                >
                    View on Spotify
                </a>
            </div>
        </div>
    );
};

export default ProfileCard;
