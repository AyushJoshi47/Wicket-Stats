(() => {
    function ensureModalStyles() {
        if (document.getElementById("authSharedModalStyles")) return;
        const style = document.createElement("style");
        style.id = "authSharedModalStyles";
        style.textContent = `
            #signinModal.modal-overlay {
                position: fixed !important;
                inset: 0 !important;
                background: rgba(185, 205, 236, 0.28) !important;
                backdrop-filter: blur(8px) !important;
                -webkit-backdrop-filter: blur(8px) !important;
                z-index: 9999 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                opacity: 0 !important;
                visibility: hidden !important;
                transition: opacity .28s ease, visibility .28s ease !important;
            }
            #signinModal.modal-overlay.active {
                opacity: 1 !important;
                visibility: visible !important;
            }
            #signinModal .modal-wrapper {
                width: min(92vw, 420px) !important;
                display: flex !important;
                justify-content: center !important;
            }
            #signinModal .modal-box {
                width: 100% !important;
                border-radius: 22px !important;
                padding: 18px 20px 16px !important;
                background: rgba(255, 255, 255, 0.72) !important;
                border: 1px solid rgba(255, 255, 255, 0.7) !important;
                box-shadow: 0 30px 80px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255,255,255,.7) !important;
                backdrop-filter: blur(22px) saturate(1.2) !important;
                -webkit-backdrop-filter: blur(22px) saturate(1.2) !important;
                color: #0f172a !important;
                position: relative !important;
                max-height: 90vh !important;
                overflow: auto !important;
            }
            #signinModal .modal-title {
                margin: 2px 0 12px !important;
                text-align: center !important;
                font-size: 34px !important;
                line-height: 1.08 !important;
                font-weight: 700 !important;
                letter-spacing: -0.5px !important;
                color: #000 !important;
            }
            #signinModal .close {
                position: absolute !important;
                right: 12px !important;
                top: 8px !important;
                font-size: 30px !important;
                line-height: 1 !important;
                cursor: pointer !important;
                color: #111 !important;
                opacity: .92 !important;
                user-select: none !important;
                font-weight: 300 !important;
            }
            #signinModal .form-group {
                margin-bottom: 10px !important;
            }
            #signinModal .form-group label {
                display: block !important;
                margin-bottom: 5px !important;
                font-size: 12px !important;
                letter-spacing: .4px !important;
                text-transform: uppercase !important;
                font-weight: 800 !important;
                color: #000 !important;
            }
            #signinModal .form-group input,
            #signinModal .form-group select,
            #signinModal .custom-select-trigger {
                width: 100% !important;
                min-height: 44px !important;
                border: 1px solid rgba(167, 190, 222, 0.55) !important;
                border-radius: 12px !important;
                padding: 0 12px !important;
                font-size: 14px !important;
                background: rgba(255,255,255,0.9) !important;
                color: #111 !important;
                box-shadow: inset 0 1px 0 rgba(255,255,255,.8) !important;
            }
            #signinModal .form-group input::placeholder {
                color: rgba(0,0,0,0.42) !important;
            }
            #signinModal .custom-select-wrapper {
                width: 100% !important;
            }
            #signinModal .custom-options {
                border-radius: 10px !important;
                margin-top: 6px !important;
                border: 1px solid rgba(167, 190, 222, 0.55) !important;
                background: rgba(255,255,255,0.95) !important;
            }
            #signinModal .custom-option {
                font-size: 14px !important;
                padding: 8px 10px !important;
            }
            #signinModal .form-submit {
                width: 100% !important;
                min-height: 46px !important;
                margin-top: 6px !important;
                border: none !important;
                border-radius: 12px !important;
                background: #000 !important;
                color: #fff !important;
                font-size: 16px !important;
                font-weight: 700 !important;
                letter-spacing: 0 !important;
                cursor: pointer !important;
                text-transform: none !important;
            }
            #signinModal .toggle-link {
                margin-top: 10px !important;
                text-align: center !important;
                font-size: 13px !important;
                color: rgba(0, 0, 0, 0.84) !important;
            }
            #signinModal .toggle-link a {
                color: #000 !important;
                text-decoration: underline !important;
                font-weight: 700 !important;
                cursor: pointer !important;
            }
            #signinModal #signupOtpMeta,
            #signinModal #fpOtpMeta {
                font-size: 12px !important;
                color: #1f2937 !important;
            }
            #signinModal #signupResendOtpBtn,
            #signinModal #fpResendOtpBtn {
                border: 1px solid rgba(0,0,0,.2) !important;
                border-radius: 8px !important;
                padding: 4px 8px !important;
                background: rgba(255,255,255,.9) !important;
                font-size: 12px !important;
            }
            @media (max-width: 768px) {
                #signinModal .modal-wrapper { width: min(95vw, 360px) !important; }
                #signinModal .modal-box { border-radius: 18px !important; padding: 14px 14px 12px !important; }
                #signinModal .modal-title { font-size: clamp(28px, 8vw, 34px) !important; margin-bottom: 8px !important; }
                #signinModal .close { font-size: 24px !important; right: 8px !important; top: 4px !important; }
                #signinModal .form-group label { font-size: 12px !important; margin-bottom: 5px !important; }
                #signinModal .form-group input, #signinModal .form-group select, #signinModal .custom-select-trigger { min-height: 40px !important; font-size: 13px !important; border-radius: 10px !important; padding: 0 10px !important; }
                #signinModal .custom-option { font-size: 14px !important; padding: 9px 10px !important; }
                #signinModal .form-submit { min-height: 42px !important; font-size: 14px !important; border-radius: 10px !important; }
                #signinModal .toggle-link { font-size: 12px !important; margin-top: 8px !important; }
                #signinModal #signupOtpMeta, #signinModal #fpOtpMeta { font-size: 12px !important; }
            }
        `;
        document.head.appendChild(style);
    }

    function ensureModalMarkup() {
        if (document.getElementById("signinModal")) return;
        const hasRegisterTrigger = document.getElementById("registerLink") || document.querySelector('a.btn-register[href="#"]');
        if (!hasRegisterTrigger) return;

        const wrapper = document.createElement("div");
        wrapper.className = "modal-overlay";
        wrapper.id = "signinModal";
        wrapper.innerHTML = `
            <div class="modal-wrapper">
                <div class="modal-box">
                    <span class="close">&times;</span>
                    <div id="signInForm">
                        <h2 class="modal-title">Sign In</h2>
                        <form id="loginForm">
                            <div class="form-group">
                                <label for="si-email">Email Address</label>
                                <input type="email" name="email" id="si-email" placeholder="you@example.com" required>
                            </div>
                            <div class="form-group">
                                <label for="si-pass">Password</label>
                                <input type="password" name="password" id="si-pass" placeholder="********" required>
                            </div>
                            <button type="submit" class="form-submit">Sign In</button>
                        </form>
                        <div class="toggle-link"><a id="showForgotPassword">Forgot password?</a></div>
                        <div class="toggle-link">Don't have an account? <a id="showSignUp">Sign Up</a></div>
                    </div>
                    <div id="forgotPasswordForm" style="display:none;">
                        <h2 class="modal-title">Forgot Password</h2>
                        <form id="forgotPasswordFormEl">
                            <div class="form-group">
                                <label for="fp-email">Email Address</label>
                                <input type="email" name="email" id="fp-email" placeholder="you@example.com" required>
                            </div>
                            <div class="form-group" id="fpOtpSection" style="display:none;">
                                <label for="fp-otp">Enter OTP</label>
                                <input type="text" name="otp" id="fp-otp" placeholder="6-digit code">
                            </div>
                            <div id="fpOtpMeta" style="display:none; margin: 6px 0 10px; font-size: 12px;">
                                <span id="fpOtpTimer">OTP expires in 05:00</span>
                                <button type="button" id="fpResendOtpBtn" style="margin-left:10px;" disabled>Resend OTP</button>
                            </div>
                            <div id="fpResetSection" style="display:none;">
                                <div class="form-group">
                                    <label for="fp-new-pass">New Password</label>
                                    <input type="password" id="fp-new-pass" name="new_password" placeholder="Enter new password">
                                </div>
                                <div class="form-group">
                                    <label for="fp-confirm-pass">Confirm New Password</label>
                                    <input type="password" id="fp-confirm-pass" name="confirm_password" placeholder="Re-enter new password">
                                </div>
                            </div>
                            <button type="button" id="fpActionBtn" class="form-submit">Send OTP</button>
                            <button type="submit" id="fpResetBtn" class="form-submit" style="display:none;">Reset Password</button>
                        </form>
                        <div class="toggle-link">Back to <a id="backToSignInFromForgot">Sign In</a></div>
                    </div>
                    <div id="signUpFormContainer" style="display:none;">
                        <h2 class="modal-title">Sign Up</h2>
                        <form id="signUpForm">
                            <div class="form-group">
                                <label for="name">Full Name</label>
                                <input type="text" name="name" id="name" placeholder="John Doe" required>
                            </div>
                            <div class="form-group">
                                <label for="email">Email Address</label>
                                <input type="email" name="email" id="email" placeholder="you@example.com" required>
                            </div>
                            <div class="form-group">
                                <label for="password">Password</label>
                                <input type="password" name="password" id="password" placeholder="********" required>
                            </div>
                            <div class="form-group" id="otpSection" style="display:none;">
                                <label for="otp">Enter OTP</label>
                                <input type="text" name="otp" id="otp" placeholder="6-digit code">
                            </div>
                            <div id="signupOtpMeta" style="display:none; margin: 6px 0 10px; font-size: 12px;">
                                <span id="signupOtpTimer">OTP expires in 05:00</span>
                                <button type="button" id="signupResendOtpBtn" style="margin-left:10px;" disabled>Resend OTP</button>
                            </div>
                            <button type="button" id="actionBtn" class="form-submit">Generate OTP</button>
                            <button type="submit" id="signUpSubmitBtn" class="form-submit" style="display:none;">Create Account</button>
                        </form>
                        <div class="toggle-link">Already have an account? <a id="showSignIn">Sign In</a></div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(wrapper);
    }

    function initCustomPlanSelect() {
        const customSelect = document.getElementById("customPlanSelect");
        if (!customSelect) return;

        const trigger = customSelect.querySelector(".custom-select-trigger");
        const text = customSelect.querySelector(".custom-select-text");
        const options = customSelect.querySelectorAll(".custom-option");
        const hiddenSelect = document.getElementById("plan");

        if (!trigger || !text || !hiddenSelect || options.length === 0) return;

        trigger.addEventListener("click", (e) => {
            e.stopPropagation();
            customSelect.classList.toggle("open");
        });

        options.forEach((opt) => {
            opt.addEventListener("click", (e) => {
                e.stopPropagation();
                const val = opt.getAttribute("data-value") || "";
                text.innerHTML = opt.innerHTML;
                hiddenSelect.value = val;
                hiddenSelect.dispatchEvent(new Event("change"));
                options.forEach((o) => o.classList.remove("selected"));
                opt.classList.add("selected");
                customSelect.classList.remove("open");
                if (window.lucide && typeof window.lucide.createIcons === "function") {
                    window.lucide.createIcons();
                }
            });
        });

        document.addEventListener("click", () => customSelect.classList.remove("open"));
    }

    function initAuthShared() {
        const modal = document.getElementById("signinModal");
        if (!modal) return;

        const registerLink = document.getElementById("registerLink") || document.querySelector('a.btn-register[href="#"]');
        const bandRegisterBtn = document.getElementById("bandRegisterBtn");
        const closeBtn = modal.querySelector(".close");
        const signInForm = document.getElementById("signInForm");
        const signUpForm = document.getElementById("signUpFormContainer");
        const forgotPasswordForm = document.getElementById("forgotPasswordForm");
        const showSignUp = document.getElementById("showSignUp");
        const showSignIn = document.getElementById("showSignIn");
        const showForgotPassword = document.getElementById("showForgotPassword");
        const backToSignInFromForgot = document.getElementById("backToSignInFromForgot");

        const generateOtpBtn = document.getElementById("actionBtn");
        const signUpSubmitBtn = document.getElementById("signUpSubmitBtn");
        const otpSection = document.getElementById("otpSection");
        const planSection = document.getElementById("planSection");
        const otpInput = document.getElementById("otp");
        const planSelect = document.getElementById("plan");
        const planSelectText = document.querySelector("#customPlanSelect .custom-select-text");
        const signupOtpMeta = document.getElementById("signupOtpMeta");
        const signupOtpTimer = document.getElementById("signupOtpTimer");
        const signupResendOtpBtn = document.getElementById("signupResendOtpBtn");

        const forgotPasswordFormEl = document.getElementById("forgotPasswordFormEl");
        const fpEmail = document.getElementById("fp-email");
        const fpOtpSection = document.getElementById("fpOtpSection");
        const fpOtpInput = document.getElementById("fp-otp");
        const fpOtpMeta = document.getElementById("fpOtpMeta");
        const fpOtpTimer = document.getElementById("fpOtpTimer");
        const fpResendOtpBtn = document.getElementById("fpResendOtpBtn");
        const fpActionBtn = document.getElementById("fpActionBtn");
        const fpResetSection = document.getElementById("fpResetSection");
        const fpResetBtn = document.getElementById("fpResetBtn");
        const fpNewPass = document.getElementById("fp-new-pass");
        const fpConfirmPass = document.getElementById("fp-confirm-pass");

        const signUpSubmitDefaultText = signUpSubmitBtn ? signUpSubmitBtn.innerText : "Create Account";
        let signupOtpVerified = false;
        let forgotOtpVerified = false;
        let signupOtpTimerHandle = null;
        let forgotOtpTimerHandle = null;

        function formatCountdown(totalSeconds) {
            const min = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
            const sec = (totalSeconds % 60).toString().padStart(2, "0");
            return `${min}:${sec}`;
        }

        function startOtpTimer(kind, seconds) {
            const isSignup = kind === "signup";
            const timerEl = isSignup ? signupOtpTimer : fpOtpTimer;
            const resendBtn = isSignup ? signupResendOtpBtn : fpResendOtpBtn;
            let remaining = Math.max(0, Number(seconds) || 300);

            if (isSignup && signupOtpTimerHandle) clearInterval(signupOtpTimerHandle);
            if (!isSignup && forgotOtpTimerHandle) clearInterval(forgotOtpTimerHandle);

            if (resendBtn) resendBtn.disabled = true;
            if (timerEl) timerEl.textContent = `OTP expires in ${formatCountdown(remaining)}`;

            const tick = () => {
                remaining -= 1;
                if (remaining <= 0) {
                    if (timerEl) timerEl.textContent = "OTP expired";
                    if (resendBtn) resendBtn.disabled = false;
                    if (isSignup && signupOtpTimerHandle) {
                        clearInterval(signupOtpTimerHandle);
                        signupOtpTimerHandle = null;
                    }
                    if (!isSignup && forgotOtpTimerHandle) {
                        clearInterval(forgotOtpTimerHandle);
                        forgotOtpTimerHandle = null;
                    }
                    return;
                }
                if (timerEl) timerEl.textContent = `OTP expires in ${formatCountdown(remaining)}`;
            };

            const timerRef = setInterval(tick, 1000);
            if (isSignup) signupOtpTimerHandle = timerRef;
            else forgotOtpTimerHandle = timerRef;
        }

        function showSignInView() {
            if (signUpForm) signUpForm.style.display = "none";
            if (forgotPasswordForm) forgotPasswordForm.style.display = "none";
            if (signInForm) signInForm.style.display = "block";
        }

        function showSignUpView() {
            if (signInForm) signInForm.style.display = "none";
            if (forgotPasswordForm) forgotPasswordForm.style.display = "none";
            if (signUpForm) signUpForm.style.display = "block";
            resetSignupFlow();
        }

        function showForgotPasswordView() {
            if (signInForm) signInForm.style.display = "none";
            if (signUpForm) signUpForm.style.display = "none";
            if (forgotPasswordForm) forgotPasswordForm.style.display = "block";
            resetForgotFlow();
        }

        function resetSignupFlow() {
            signupOtpVerified = false;
            if (signupOtpTimerHandle) {
                clearInterval(signupOtpTimerHandle);
                signupOtpTimerHandle = null;
            }
            if (otpSection) otpSection.style.display = "none";
            if (signupOtpMeta) signupOtpMeta.style.display = "none";
            if (signupResendOtpBtn) signupResendOtpBtn.disabled = true;
            if (otpInput) {
                otpInput.required = false;
                otpInput.value = "";
            }
            if (planSection) planSection.style.display = "none";
            if (planSelect) {
                planSelect.required = false;
                planSelect.value = "";
            }
            if (planSelectText) planSelectText.textContent = "SELECT YOUR PLAN";
            if (generateOtpBtn) {
                generateOtpBtn.style.display = "inline-block";
                generateOtpBtn.disabled = false;
                generateOtpBtn.innerText = "Generate OTP";
            }
            if (signUpSubmitBtn) signUpSubmitBtn.style.display = "none";
        }

        function resetForgotFlow() {
            forgotOtpVerified = false;
            if (forgotOtpTimerHandle) {
                clearInterval(forgotOtpTimerHandle);
                forgotOtpTimerHandle = null;
            }
            if (fpOtpSection) fpOtpSection.style.display = "none";
            if (fpOtpMeta) fpOtpMeta.style.display = "none";
            if (fpResetSection) fpResetSection.style.display = "none";
            if (fpOtpInput) {
                fpOtpInput.required = false;
                fpOtpInput.value = "";
            }
            if (fpNewPass) {
                fpNewPass.required = false;
                fpNewPass.value = "";
            }
            if (fpConfirmPass) {
                fpConfirmPass.required = false;
                fpConfirmPass.value = "";
            }
            if (fpActionBtn) {
                fpActionBtn.style.display = "inline-block";
                fpActionBtn.disabled = false;
                fpActionBtn.innerText = "Send OTP";
            }
            if (fpResetBtn) {
                fpResetBtn.style.display = "none";
                fpResetBtn.disabled = false;
                fpResetBtn.innerText = "Reset Password";
            }
        }

        function closeModalAndReset() {
            modal.classList.remove("active");
            showSignInView();
            resetSignupFlow();
            resetForgotFlow();
        }

        function openModalWithView(view) {
            modal.classList.add("active");
            if ((view || "").toLowerCase() === "signin") {
                showSignInView();
                return;
            }
            showSignUpView();
        }

        function updateRegisterLink(loggedIn = true) {
            const link = document.getElementById("registerLink") || document.querySelector('a.btn-register[href="#"]');
            if (!link) return;
            if (loggedIn) {
                link.textContent = "Dashboard";
                link.href = "/dashboard";
            } else {
                link.textContent = "Register";
                link.href = "#";
            }
        }

        async function syncAuthState() {
            try {
                const response = await fetch("/api/auth-status", { cache: "no-store" });
                const data = await response.json();
                if (response.ok && data.status === "success") {
                    updateRegisterLink(!!data.logged_in);
                    if (data.logged_in) closeModalAndReset();
                }
            } catch (err) {
                console.error("Auth sync failed:", err);
            }
        }

        async function completeRegistration(paymentData = {}) {
            const signUpFormEl = document.getElementById("signUpForm");
            if (!signUpFormEl) throw new Error("Sign up form not found");

            const formData = new FormData(signUpFormEl);
            formData.append("razorpay_order_id", paymentData.razorpay_order_id || "");
            formData.append("razorpay_payment_id", paymentData.razorpay_payment_id || "");
            formData.append("razorpay_signature", paymentData.razorpay_signature || "");

            const response = await fetch("/register", {
                method: "POST",
                body: formData
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.status !== "success") {
                throw new Error(data.message || "Registration failed");
            }
            updateRegisterLink();
            window.location.href = data.redirect || "/dashboard";
        }

        if (registerLink) {
            registerLink.addEventListener("click", (e) => {
                if (registerLink.tagName === "BUTTON" || registerLink.getAttribute("href") === "#") {
                    e.preventDefault();
                    openModalWithView("signup");
                }
            });
        }

        if (bandRegisterBtn) {
            bandRegisterBtn.addEventListener("click", (e) => {
                e.preventDefault();
                openModalWithView("signup");
            });
        }

        document.querySelectorAll("[data-auth-open]").forEach((trigger) => {
            trigger.addEventListener("click", (e) => {
                const href = (trigger.getAttribute("href") || "").trim();
                if (href && href !== "#") return;
                e.preventDefault();
                openModalWithView(trigger.getAttribute("data-auth-open") || "signup");
            });
        });

        if (closeBtn) closeBtn.onclick = closeModalAndReset;

        window.addEventListener("click", (e) => {
            if (e.target === modal) closeModalAndReset();
        });

        if (showSignUp) {
            showSignUp.onclick = (e) => {
                e.preventDefault();
                showSignUpView();
            };
        }

        if (showSignIn) {
            showSignIn.onclick = (e) => {
                e.preventDefault();
                showSignInView();
            };
        }

        if (showForgotPassword) {
            showForgotPassword.onclick = (e) => {
                e.preventDefault();
                showForgotPasswordView();
            };
        }

        if (backToSignInFromForgot) {
            backToSignInFromForgot.onclick = (e) => {
                e.preventDefault();
                showSignInView();
            };
        }

        if (generateOtpBtn) {
            generateOtpBtn.addEventListener("click", async () => {
                const nameEl = document.getElementById("name");
                const emailEl = document.getElementById("email");
                const passwordEl = document.getElementById("password");
                const name = (nameEl?.value || "").trim();
                const email = (emailEl?.value || "").trim().toLowerCase();
                const password = (passwordEl?.value || "").trim();
                const otpValue = (otpInput?.value || "").trim();
                if (!name || !email || !password) {
                    alert("Please fill name, email, and password before generating OTP.");
                    return;
                }

                if (!otpSection || otpSection.style.display === "none") {
                    generateOtpBtn.disabled = true;
                    generateOtpBtn.innerText = "Sending...";
                    try {
                        const response = await fetch("/send-otp", {
                            method: "POST",
                            body: new URLSearchParams({ email })
                        });
                        if (!response.ok) {
                            const data = await response.json().catch(() => ({}));
                            throw new Error(data.message || "Failed to send OTP");
                        }
                        const data = await response.json().catch(() => ({}));
                        otpSection.style.display = "block";
                        if (signupOtpMeta) signupOtpMeta.style.display = "block";
                        if (otpInput) otpInput.required = true;
                        generateOtpBtn.disabled = false;
                        generateOtpBtn.innerText = "Verify OTP";
                        startOtpTimer("signup", data.expires_in || 300);
                        alert("OTP sent to your email.");
                    } catch (error) {
                        alert(error.message || "Network error");
                        generateOtpBtn.disabled = false;
                        generateOtpBtn.innerText = "Generate OTP";
                    }
                    return;
                }

                if (!/^\d{6}$/.test(otpValue)) {
                    alert("Please enter a valid 6-digit OTP.");
                    return;
                }

                generateOtpBtn.disabled = true;
                generateOtpBtn.innerText = "Verifying...";
                try {
                    const response = await fetch("/verify-otp", {
                        method: "POST",
                        body: new URLSearchParams({ email, otp: otpValue })
                    });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok || data.status !== "success") {
                        throw new Error(data.message || "OTP verification failed");
                    }
                    signupOtpVerified = true;
                    if (signupOtpTimerHandle) {
                        clearInterval(signupOtpTimerHandle);
                        signupOtpTimerHandle = null;
                    }
                    if (planSection) planSection.style.display = "block";
                    if (planSelect) planSelect.required = true;
                    if (signupOtpMeta) signupOtpMeta.style.display = "none";
                    generateOtpBtn.style.display = "none";
                    if (signUpSubmitBtn) signUpSubmitBtn.style.display = "inline-block";
                    alert("OTP verified. Select a plan and continue.");
                } catch (error) {
                    alert(error.message || "Failed to verify OTP");
                    generateOtpBtn.disabled = false;
                    generateOtpBtn.innerText = "Verify OTP";
                }
            });
        }

        if (signupResendOtpBtn) {
            signupResendOtpBtn.addEventListener("click", async () => {
                const emailEl = document.getElementById("email");
                const email = (emailEl?.value || "").trim().toLowerCase();
                if (!email) {
                    alert("Enter your email first.");
                    return;
                }
                signupResendOtpBtn.disabled = true;
                try {
                    const response = await fetch("/send-otp", {
                        method: "POST",
                        body: new URLSearchParams({ email })
                    });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok) {
                        throw new Error(data.message || "Failed to resend OTP");
                    }
                    startOtpTimer("signup", data.expires_in || 300);
                    if (otpInput) otpInput.value = "";
                    alert("OTP resent successfully.");
                } catch (error) {
                    alert(error.message || "Failed to resend OTP");
                    signupResendOtpBtn.disabled = false;
                }
            });
        }

        if (fpActionBtn) {
            fpActionBtn.addEventListener("click", async () => {
                const email = (fpEmail?.value || "").trim().toLowerCase();
                const otpValue = (fpOtpInput?.value || "").trim();
                if (!email) {
                    alert("Please enter your email first.");
                    return;
                }

                if (!fpOtpSection || fpOtpSection.style.display === "none") {
                    fpActionBtn.disabled = true;
                    fpActionBtn.innerText = "Sending...";
                    try {
                        const response = await fetch("/forgot-password/send-otp", {
                            method: "POST",
                            body: new URLSearchParams({ email })
                        });
                        const data = await response.json().catch(() => ({}));
                        if (!response.ok || data.status !== "success") {
                            throw new Error(data.message || "Failed to send OTP");
                        }
                        fpOtpSection.style.display = "block";
                        if (fpOtpInput) fpOtpInput.required = true;
                        if (fpOtpMeta) fpOtpMeta.style.display = "block";
                        fpActionBtn.disabled = false;
                        fpActionBtn.innerText = "Verify OTP";
                        startOtpTimer("forgot", data.expires_in || 300);
                        alert("OTP sent to your email.");
                    } catch (error) {
                        alert(error.message || "Failed to send OTP");
                        fpActionBtn.disabled = false;
                        fpActionBtn.innerText = "Send OTP";
                    }
                    return;
                }

                if (!/^\d{6}$/.test(otpValue)) {
                    alert("Please enter a valid 6-digit OTP.");
                    return;
                }

                fpActionBtn.disabled = true;
                fpActionBtn.innerText = "Verifying...";
                try {
                    const response = await fetch("/forgot-password/verify-otp", {
                        method: "POST",
                        body: new URLSearchParams({ email, otp: otpValue })
                    });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok || data.status !== "success") {
                        throw new Error(data.message || "OTP verification failed");
                    }
                    forgotOtpVerified = true;
                    if (forgotOtpTimerHandle) {
                        clearInterval(forgotOtpTimerHandle);
                        forgotOtpTimerHandle = null;
                    }
                    if (fpOtpMeta) fpOtpMeta.style.display = "none";
                    if (fpResetSection) fpResetSection.style.display = "block";
                    if (fpNewPass) fpNewPass.required = true;
                    if (fpConfirmPass) fpConfirmPass.required = true;
                    fpActionBtn.style.display = "none";
                    if (fpResetBtn) fpResetBtn.style.display = "inline-block";
                    alert("OTP verified. Enter your new password.");
                } catch (error) {
                    alert(error.message || "Failed to verify OTP");
                    fpActionBtn.disabled = false;
                    fpActionBtn.innerText = "Verify OTP";
                }
            });
        }

        if (fpResendOtpBtn) {
            fpResendOtpBtn.addEventListener("click", async () => {
                const email = (fpEmail?.value || "").trim().toLowerCase();
                if (!email) {
                    alert("Enter your email first.");
                    return;
                }
                fpResendOtpBtn.disabled = true;
                try {
                    const response = await fetch("/forgot-password/send-otp", {
                        method: "POST",
                        body: new URLSearchParams({ email })
                    });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok || data.status !== "success") {
                        throw new Error(data.message || "Failed to resend OTP");
                    }
                    startOtpTimer("forgot", data.expires_in || 300);
                    if (fpOtpInput) fpOtpInput.value = "";
                    alert("OTP resent successfully.");
                } catch (error) {
                    alert(error.message || "Failed to resend OTP");
                    fpResendOtpBtn.disabled = false;
                }
            });
        }

        if (forgotPasswordFormEl) {
            forgotPasswordFormEl.addEventListener("submit", async (e) => {
                e.preventDefault();
                if (!forgotOtpVerified) {
                    alert("Please verify OTP first.");
                    return;
                }
                const email = (fpEmail?.value || "").trim().toLowerCase();
                const newPassword = (fpNewPass?.value || "").trim();
                const confirmPassword = (fpConfirmPass?.value || "").trim();
                if (!email || !newPassword || !confirmPassword) {
                    alert("All fields are required.");
                    return;
                }
                if (newPassword !== confirmPassword) {
                    alert("Passwords do not match.");
                    return;
                }

                if (fpResetBtn) {
                    fpResetBtn.disabled = true;
                    fpResetBtn.innerText = "Updating...";
                }
                try {
                    const response = await fetch("/forgot-password/reset", {
                        method: "POST",
                        body: new URLSearchParams({
                            email,
                            new_password: newPassword,
                            confirm_password: confirmPassword
                        })
                    });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok || data.status !== "success") {
                        throw new Error(data.message || "Failed to reset password");
                    }
                    alert("Password changed successfully. Please sign in again.");
                    window.location.reload();
                } catch (error) {
                    alert(error.message || "Failed to reset password");
                } finally {
                    if (fpResetBtn) {
                        fpResetBtn.disabled = false;
                        fpResetBtn.innerText = "Reset Password";
                    }
                }
            });
        }

        const signUpFormEl = document.getElementById("signUpForm");
        if (signUpFormEl) {
            signUpFormEl.addEventListener("submit", async (e) => {
                e.preventDefault();
                if (!signupOtpVerified) {
                    alert("Please verify OTP first.");
                    return;
                }

                const formData = new FormData(signUpFormEl);
                const payload = {
                    name: (formData.get("name") || "").toString().trim(),
                    email: (formData.get("email") || "").toString().trim(),
                    password: (formData.get("password") || "").toString().trim(),
                    otp: (formData.get("otp") || "").toString().trim(),
                    plan: (formData.get("plan") || "").toString().trim()
                };

                if (!payload.plan && planSelect) {
                    alert("Please select a plan.");
                    return;
                }
                if (!payload.plan) payload.plan = "Basic";

                if (signUpSubmitBtn) {
                    signUpSubmitBtn.disabled = true;
                    signUpSubmitBtn.innerText = "Processing...";
                }
                try {
                    const orderRes = await fetch("/register/create-order", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });
                    const orderData = await orderRes.json().catch(() => ({}));
                    if (!orderRes.ok || orderData.status !== "success") {
                        throw new Error(orderData.message || "Unable to create order");
                    }

                    if (!orderData.requires_payment || Number(orderData.amount || 0) <= 0) {
                        await completeRegistration();
                        return;
                    }

                    if (typeof window.Razorpay !== "function") {
                        throw new Error("Payment library is not loaded");
                    }

                    const options = {
                        key: orderData.key_id,
                        amount: orderData.amount,
                        currency: orderData.currency,
                        name: "WicketStats",
                        description: `${payload.plan} Plan Subscription`,
                        order_id: orderData.order_id,
                        handler: async (response) => {
                            try {
                                await completeRegistration(response);
                            } catch (err) {
                                alert(err.message || "Payment done but registration failed");
                            }
                        },
                        prefill: {
                            name: payload.name,
                            email: payload.email
                        },
                        theme: {
                            color: "#2563eb"
                        }
                    };
                    const rzp = new window.Razorpay(options);
                    rzp.on("payment.failed", (response) => {
                        const message = response?.error?.description || "Payment failed";
                        alert(`Payment failed: ${message}`);
                    });
                    rzp.open();
                } catch (err) {
                    alert(err.message || "Registration failed");
                } finally {
                    if (signUpSubmitBtn) {
                        signUpSubmitBtn.disabled = false;
                        signUpSubmitBtn.innerText = signUpSubmitDefaultText;
                    }
                }
            });
        }

        const loginFormEl = document.getElementById("loginForm");
        if (loginFormEl) {
            loginFormEl.addEventListener("submit", async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);

                const response = await fetch("/login", { method: "POST", body: formData });
                if (response.ok) {
                    updateRegisterLink();
                    closeModalAndReset();
                    window.location.href = "/dashboard";
                    return;
                }
                const data = await response.json().catch(() => ({}));
                alert(data.message || "Login failed");
            });
        }

        window.addEventListener("pageshow", () => {
            closeModalAndReset();
            syncAuthState();
        });
        window.addEventListener("popstate", () => {
            closeModalAndReset();
            syncAuthState();
        });

        syncAuthState();
    }

    document.addEventListener("DOMContentLoaded", () => {
        ensureModalStyles();
        ensureModalMarkup();
        initCustomPlanSelect();
        initAuthShared();
    });
})();
