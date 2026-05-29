const teams = {
    "Chennai Super Kings": { img: "static/images/csk.png" },
    "Mumbai Indians": { img: "static/images/mi.png" },
    "Royal Challengers Bengalore": { img: "static/images/rcb.png" },
    "Kolkata Knight Riders": { img: "static/images/kkr.png" },
    "Delhi Capitals": { img: "static/images/dc.png" },
    "   Kings XI Punjab": { img: "static/images/pbks.png" },
    "Rajasthan Royals": { img: "static/images/rr.png" },
    "Sunrisers Hyderabad": { img: "static/images/srh.png" },
    "Gujarat Titans": { img: "static/images/gt.png" },
    "Lucknow Super Giants": { img: "static/images/lsg.png" }
};

function update(selectId, cardId, imgId, nameId) {
    const val = document.getElementById(selectId).value;
    const card = document.getElementById(cardId);
    const img = document.getElementById(imgId);
    const name = document.getElementById(nameId);

    if (val && teams[val]) {
        card.classList.add("active");
        img.src = teams[val].img;
        if (name) name.textContent = val; 
    } else {
        card.classList.remove("active");
        img.src = "";
        if (name) name.textContent = "";
    }
}

// 1. Set up the event listeners
document.getElementById("team1").addEventListener("change", () => update("team1", "card1", "img1", "name1"));
document.getElementById("team2").addEventListener("change", () => update("team2", "card2", "img2", "name2"));

// 2. RUN IMMEDIATELY on load
update("team1", "card1", "img1", "name1");
update("team2", "card2", "img2", "name2");

const generateBtn = document.querySelector(".predict");
if (generateBtn) {
    generateBtn.addEventListener("click", async () => {
        const team1 = document.getElementById("team1").value;
        const team2 = document.getElementById("team2").value;

        if (!team1 || !team2) {
            alert("Please select both teams!");
            return;
        }

        generateBtn.innerText = "Analyzing Match Data...";
        generateBtn.disabled = true;

        const resultsEl = document.getElementById("predictionResults");

        try {
            const response = await fetch("/predict", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify({team1, team2})
            });

            const d = await response.json();

            // Populate results
            document.getElementById("winner").innerText = d.predicted_winner ?? "-";
            document.getElementById("confidenceGap").innerText = d.confidence_gap ?? "-";
            
            const t1Prob = d.team1_prediction_score ?? 0;
            const t2Prob = d.team2_prediction_score ?? 0;

            document.getElementById("team1ProbBar").style.width = t1Prob + "%";
            document.getElementById("team2ProbBar").style.width = t2Prob + "%";

            document.getElementById("team1ProbLabel").innerText = `${d.team1 ?? "-"}: ${t1Prob}%`;
            document.getElementById("team2ProbLabel").innerText = `${d.team2 ?? "-"}: ${t2Prob}%`;

            // 2. Head to Head
            document.getElementById("totalMatches").innerText = d.total_matches ?? 0;
            document.getElementById("team1Display").innerText = d.team1 ?? "-";
            document.getElementById("team2Display").innerText = d.team2 ?? "-";
            document.getElementById("team1Wins").innerText = d.team1_wins ?? 0;
            document.getElementById("team2Wins").innerText = d.team2_wins ?? 0;
            
            const totalWins = (d.team1_wins ?? 0) + (d.team2_wins ?? 0);
            const t1WinPerc = totalWins > 0 ? ((d.team1_wins ?? 0) / totalWins) * 100 : 0;
            const t2WinPerc = totalWins > 0 ? ((d.team2_wins ?? 0) / totalWins) * 100 : 0;

            document.getElementById("team1WinBar").style.width = t1WinPerc + "%";
            document.getElementById("team2WinBar").style.width = t2WinPerc + "%";

            // 3. Batting Prowess
            document.getElementById("avgTeam1Score").innerText = d.team1_average_runs ?? 0;
            document.getElementById("avgTeam2Score").innerText = d.team2_average_runs ?? 0;
            document.getElementById("totalTeam1Runs").innerText = d.total_team1_runs ?? 0;
            document.getElementById("totalTeam2Runs").innerText = d.total_team2_runs ?? 0;
            document.getElementById("ppAvg1").innerText = d.team1_powerplay_avg ?? 0;
            document.getElementById("ppAvg2").innerText = d.team2_powerplay_avg ?? 0;
            document.getElementById("deathAvg1").innerText = d.team1_death_avg ?? 0;
            document.getElementById("deathAvg2").innerText = d.team2_death_avg ?? 0;

            // 4. Toss Intelligence
            document.getElementById("team1TossName").innerText = d.team1 ?? "-";
            document.getElementById("team2TossName").innerText = d.team2 ?? "-";
            document.getElementById("tossWins1").innerText = d.team1_toss_wins ?? 0;
            document.getElementById("tossWins2").innerText = d.team2_toss_wins ?? 0;
            document.getElementById("tossMatchWon1").innerText = d.team1_toss_match_won ?? 0;
            document.getElementById("tossMatchWon2").innerText = d.team2_toss_match_won ?? 0;

            // 5. Extreme Records
            document.getElementById("team1ExtName").innerText = d.team1 ?? "-";
            document.getElementById("team2ExtName").innerText = d.team2 ?? "-";
            document.getElementById("team1Hi").innerText = d.team1_highest_score ?? 0;
            document.getElementById("team1HiWon").innerText = `Result: ${d.team1_highest_score_won_by ?? "-"}`;
            document.getElementById("team1Lo").innerText = d.team1_lowest_score ?? 0;
            document.getElementById("team1LoWon").innerText = `Result: ${d.team1_lowest_score_won_by ?? "-"}`;
            
            document.getElementById("team2Hi").innerText = d.team2_highest_score ?? 0;
            document.getElementById("team2HiWon").innerText = `Result: ${d.team2_highest_score_won_by ?? "-"}`;
            document.getElementById("team2Lo").innerText = d.team2_lowest_score ?? 0;
            document.getElementById("team2LoWon").innerText = `Result: ${d.team2_lowest_score_won_by ?? "-"}`;

            // 6. Fortress Stats
            document.getElementById("team1VenueName").innerText = d.team1 ?? "-";
            document.getElementById("team2VenueName").innerText = d.team2 ?? "-";
            document.getElementById("team1TopVenue").innerText = d.team1_top_venue || "N/A";
            document.getElementById("team1VenueWins").innerText = d.team1_top_venue_wins ?? 0;
            document.getElementById("team2TopVenue").innerText = d.team2_top_venue || "N/A";
            document.getElementById("team2VenueWins").innerText = d.team2_top_venue_wins ?? 0;

            // Show Results with animation
            if (resultsEl) {
                resultsEl.classList.add("show");
                resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                if (window.lucide) window.lucide.createIcons();
            }
        } catch (err) {
            console.error(err);
            alert("An error occurred while getting predictions.");
        } finally {
            generateBtn.innerText = "Get the predictions";
            generateBtn.disabled = false;
        }
    });
}



















document.addEventListener('DOMContentLoaded', () => {

    const modal         = document.getElementById("signinModal");
    const btn           = document.getElementById("registerLink");
    const closeBtn      = modal.querySelector(".close");
    const signInForm    = document.getElementById("signInForm");
    const signUpForm    = document.getElementById("signUpFormContainer");
    const showSignUp    = document.getElementById("showSignUp");
    const showSignIn    = document.getElementById("showSignIn");
    const generateOtpBtn  = document.getElementById('actionBtn');
    const signUpSubmitBtn = document.getElementById('signUpSubmitBtn');
    const otpSection      = document.getElementById('otpSection');

    // â”€â”€ Open modal â”€â”€
    btn.addEventListener("click", (e) => {
        e.preventDefault();
        modal.style.display = "block";
    });

    // â”€â”€ Close modal â”€â”€
    closeBtn.onclick = () => modal.style.display = "none";
    window.onclick   = (e) => { if (e.target === modal) modal.style.display = "none"; };

    // ── Switch forms ──
    if(showSignUp) {
        showSignUp.onclick = (e) => {
            e.preventDefault();
            signInForm.style.display = "none";
            signUpForm.style.display = "block";
        };
    }

    if(showSignIn) {
        showSignIn.onclick = (e) => {
            e.preventDefault();
            signUpForm.style.display = "none";
            signInForm.style.display = "block";
        };
    }

    // â”€â”€ Generate OTP â”€â”€
    generateOtpBtn.addEventListener('click', async () => {
        const email = document.getElementById('email').value.trim();
        if (!email) return alert("Please enter your email first.");

        generateOtpBtn.disabled = true;
        generateOtpBtn.innerText = "Sending...";

        try {
            const response = await fetch('/send-otp', {
                method: 'POST',
                body: new URLSearchParams({ email })
            });

            if (response.ok) {
                otpSection.style.display = 'block';
                document.getElementById('otp').required = true;
                generateOtpBtn.style.display = 'none';
                signUpSubmitBtn.style.display = 'inline-block';
                alert("OTP sent to your email!");
            } else {
                alert("Failed to send OTP");
                generateOtpBtn.disabled = false;
                generateOtpBtn.innerText = "Generate OTP";
            }
        } catch (error) {
            console.error("Error:", error);
            alert("Network error");
            generateOtpBtn.disabled = false;
            generateOtpBtn.innerText = "Generate OTP";
        }
    });

    function updateRegisterLink() {
    const registerLink = document.getElementById('registerLink');
    registerLink.textContent = 'Dashboard';
    registerLink.href = '/dashboard';
}

// After signup success
document.getElementById('signUpForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);

    const response = await fetch('/register', {
        method: 'POST',
        body: formData
    });

    if (response.ok) {
        updateRegisterLink(); // Change link immediately
        window.location.href = '/dashboard'; // Optional redirect
    } else {
        const data = await response.json();
        alert(data.message || "Registration failed");
    }
});

// Similarly, after login success
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);

    const response = await fetch('/login', { method: 'POST', body: formData });

    if (response.ok) {
        updateRegisterLink();
        window.location.href = '/dashboard'; // Optional
    } else {
        const data = await response.json();
        alert(data.message || "Login failed");
    }
});

    // Typewriter effect
    const phrases = ["stop guessing?", "start analyzing?", "make predictions?", "win your leagues?", "own the game?"];
    let phraseIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    const typewriterElement = document.getElementById('typewriter');
    
    function type() {
        if (!typewriterElement) return;
        
        const currentPhrase = phrases[phraseIndex];
        
        if (isDeleting) {
            typewriterElement.textContent = currentPhrase.substring(0, charIndex - 1);
            charIndex--;
        } else {
            typewriterElement.textContent = currentPhrase.substring(0, charIndex + 1);
            charIndex++;
        }
        
        let typeSpeed = 100;
        
        if (isDeleting) {
            typeSpeed /= 2;
        }
        
        if (!isDeleting && charIndex === currentPhrase.length) {
            typeSpeed = 2000;
            isDeleting = true;
        } else if (isDeleting && charIndex === 0) {
            isDeleting = false;
            phraseIndex = (phraseIndex + 1) % phrases.length;
            typeSpeed = 500;
        }
        
        setTimeout(type, typeSpeed);
    }
    
    if (typewriterElement) {
        type();
    }
});