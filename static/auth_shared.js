(() => {
    function ensureModalStyles() {
        if (document.getElementById("authSharedModalStyles")) return;
        const style = document.createElement("style");
        style.id = "authSharedModalStyles";
        style.textContent = `
            #signinModal.modal-overlay {
                position: fixed;
                inset: 0;
                background: rgba(244, 247, 251, 0.35);
                backdrop-filter: blur(5px);
                -webkit-backdrop-filter: blur(5px);
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.35s cubic-bezier(0.16, 1, 0.3, 1), visibility 0.35s;
            }
            #signinModal.modal-overlay.active {
                opacity: 1;
                visibility: visible;
            }
            #signinModal .modal-wrapper {
                display: flex;
                flex-direction: column;
                align-items: center;
                width: 100%;
            }
            #signinModal .modal-box {
                position: relative;
                width: 440px;
                max-width: 92vw;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.7), rgba(245, 245, 245, 0.7));
                border: 1px solid rgba(255, 255, 255, 0.4);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border-radius: 28px;
                padding: 40px 36px 36px;
                box-shadow: 0 30px 70px rgba(0, 0, 0, 0.12), inset 0 1px 1px rgba(255, 255, 255, 0.6), inset 0 -1px 1px rgba(0, 0, 0, 0.05);
                transform: translateY(20px) scale(0.97);
                transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.4s;
                opacity: 0;
                color: #000000;
                max-height: 90vh;
                overflow: auto;
            }
            #signinModal.modal-overlay.active .modal-box {
                transform: translateY(0) scale(1);
                opacity: 1;
            }
            #signinModal .modal-close,
            #signinModal .close {
                position: absolute;
                top: 20px;
                right: 20px;
                background: none;
                border: none;
                color: #000000;
                cursor: pointer;
                padding: 6px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background-color 0.2s, color 0.2s;
            }
            #signinModal .modal-close:hover,
            #signinModal .close:hover {
                background-color: rgba(0, 0, 0, 0.08);
                color: #000000;
            }
            #signinModal .modal-title {
                font-size: 2.2rem;
                text-align: center;
                margin-bottom: 24px;
                line-height: 1.1;
                font-weight: 700;
                letter-spacing: -0.5px;
                color: #000000;
            }
            #signinModal .form-group {
                margin-bottom: 20px;
                display: flex;
                flex-direction: column;
                gap: 6px;
            }
            #signinModal .form-group label {
                font-size: 12px;
                font-weight: 700;
                color: #000000;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                text-align: left;
            }
            #signinModal .form-group input,
            #signinModal .form-group select {
                width: 100%;
                background: rgba(255, 255, 255, 0.65);
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 12px;
                padding: 12px 16px;
                font-size: 15px;
                color: #000000;
                outline: none;
                transition: border-color 0.2s, box-shadow 0.2s, background-color 0.2s;
            }
            #signinModal .form-group input::placeholder {
                color: #555555;
            }
            #signinModal .form-group input:focus {
                border-color: #000000;
                background-color: #ffffff;
                box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.08);
            }
            #signinModal .custom-select-wrapper {
                position: relative;
                width: 100%;
            }
            #signinModal .custom-select-trigger {
                display: flex;
                align-items: center;
                justify-content: space-between;
                width: 100%;
                background: rgba(255, 255, 255, 0.65);
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 12px;
                padding: 12px 16px;
                font-size: 15px;
                color: #000000;
                font-weight: 550;
                cursor: pointer;
                transition: border-color 0.2s, box-shadow 0.2s, background-color 0.2s;
            }
            #signinModal .custom-select-trigger:hover {
                background: rgba(255, 255, 255, 0.85);
                border-color: rgba(0, 0, 0, 0.25);
            }
            #signinModal .custom-select-wrapper.open .custom-select-trigger {
                border-color: #000000;
                background-color: #ffffff;
                box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.08);
            }
            #signinModal .custom-select-trigger .chevron-icon {
                transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                color: #000000;
            }
            #signinModal .custom-select-wrapper.open .chevron-icon {
                transform: rotate(180deg);
            }
            #signinModal .custom-options {
                position: absolute;
                top: calc(100% + 6px);
                left: 0;
                right: 0;
                background: rgba(255, 255, 255, 0.96);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 12px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
                backdrop-filter: blur(15px);
                -webkit-backdrop-filter: blur(15px);
                opacity: 0;
                visibility: hidden;
                transform: translateY(-8px);
                transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1), transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), visibility 0.25s;
                z-index: 10000;
                overflow: hidden;
            }
            #signinModal .custom-select-wrapper.open .custom-options {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
            }
            #signinModal .custom-option {
                padding: 12px 16px;
                font-size: 15px;
                color: #000000;
                font-weight: 500;
                cursor: pointer;
                transition: background-color 0.15s, color 0.15s;
                text-align: left;
            }
            #signinModal .custom-option:hover {
                background-color: rgba(0, 0, 0, 0.06);
            }
            #signinModal .custom-option.selected {
                background-color: rgba(0, 0, 0, 0.1);
                font-weight: 600;
            }
            #signinModal .form-submit {
                width: 100%;
                padding: 14px;
                border: none;
                border-radius: 12px;
                background: #000000;
                color: #ffffff;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.15s ease, box-shadow 0.2s ease, opacity 0.2s ease;
            }
            #signinModal .form-submit:hover {
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
                transform: translateY(-1px);
            }
            #signinModal .form-submit:active {
                transform: translateY(0);
            }
            #signinModal .form-submit:disabled {
                opacity: 0.7;
                cursor: not-allowed;
                box-shadow: none;
            }
            #signinModal .toggle-link {
                margin-top: 20px;
                font-size: 14px;
                color: #333333;
                text-align: center;
            }
            #signinModal .toggle-link a {
                color: #000000;
                text-decoration: none;
                font-weight: 600;
                margin-left: 4px;
                transition: opacity 0.2s;
                cursor: pointer;
            }
            #signinModal .toggle-link a:hover {
                opacity: 0.7;
            }
            #signinModal #signupOtpMeta,
            #signinModal #fpOtpMeta {
                margin: 8px 0 14px 0;
                font-size: 0.9rem;
                color: #1f2937;
            }
            #signinModal #signupResendOtpBtn,
            #signinModal #fpResendOtpBtn {
                margin-left: 10px;
                border: 1px solid rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                padding: 4px 8px;
                background: rgba(255, 255, 255, 0.9);
                font-size: 12px;
            }
            @media (max-width: 768px) {
                #signinModal .modal-box {
                    width: 100%;
                    margin: 0 16px;
                    padding: 28px 22px 24px;
                    border-radius: 22px;
                }
                #signinModal .modal-title {
                    font-size: 1.8rem;
                }
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
                            <div class="form-group" id="planSection" style="position: relative; display:none;">
                                <label>Your Plan</label>
                                <div class="custom-select-wrapper" id="customPlanSelect">
                                    <div class="custom-select-trigger">
                                        <span class="custom-select-text">SELECT YOUR PLAN</span>
                                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="chevron-icon">
                                            <polyline points="6 9 12 15 18 9"></polyline>
                                        </svg>
                                    </div>
                                    <div class="custom-options">
                                        <div class="custom-option" data-value="Basic">Basic (&#8377;0)</div>
                                        <div class="custom-option" data-value="Plus">Plus (&#8377;499)</div>
                                        <div class="custom-option" data-value="Premium">Premium (&#8377;999)</div>
                                    </div>
                                </div>
                                <select id="plan" name="plan" style="position:absolute; width:0; height:0; opacity:0; pointer-events:none;">
                                    <option value="" selected>SELECT YOUR PLAN</option>
                                    <option value="Basic">Basic (&#8377;0)</option>
                                    <option value="Plus">Plus (&#8377;499)</option>
                                    <option value="Premium">Premium (&#8377;999)</option>
                                </select>
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
                            <button type="submit" id="signUpSubmitBtn" class="form-submit" style="display:none;">Pay &amp; Create Account</button>
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
                if (!payload.plan) {
                    alert("Please select a plan.");
                    return;
                }

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
