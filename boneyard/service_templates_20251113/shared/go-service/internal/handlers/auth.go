package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"

	"{{ module_name }}/internal/config"
	"{{ module_name }}/internal/logger"
	{{- if include_database }}
	"{{ module_name }}/internal/database"
	{{- endif }}
)

type LoginRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=6"`
}

type RegisterRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=6"`
	Name     string `json:"name" binding:"required"`
}

type AuthResponse struct {
	Token     string `json:"token"`
	ExpiresAt int64  `json:"expires_at"`
	User      User   `json:"user"`
}

type User struct {
	ID    string `json:"id"`
	Email string `json:"email"`
	Name  string `json:"name"`
}

// Login handler
func Login(cfg *config.Config, log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req LoginRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid request body",
				"details": err.Error(),
			})
			return
		}

		// TODO: Implement actual authentication logic
		// For production, implement:
		// 1. Hash password verification
		// 2. Database user lookup
		// 3. Rate limiting
		// 4. Account lockout policies
		// 5. Multi-factor authentication

		{{- if include_database }}
		// Database authentication example:
		// user, err := dbManager.GetUserByEmail(req.Email)
		// if err != nil {
		//     log.Errorf("Database error: %v", err)
		//     c.JSON(http.StatusInternalServerError, gin.H{"error": "Authentication service unavailable"})
		//     return
		// }
		// if user == nil || !verifyPassword(req.Password, user.PasswordHash) {
		//     c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid credentials"})
		//     return
		// }
		{{- else }}
		// Mock authentication - replace with real implementation
		{{- endif }}

		// For now, this is a mock implementation
		if req.Email != "admin@example.com" || req.Password != "password" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Invalid credentials",
			})
			return
		}

		// Generate JWT token
		token, expiresAt, err := generateToken(cfg.JWTSecret, "1", req.Email)
		if err != nil {
			log.Errorf("Failed to generate token: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to generate token",
			})
			return
		}

		user := User{
			ID:    "1",
			Email: req.Email,
			Name:  "Admin User",
		}

		c.JSON(http.StatusOK, AuthResponse{
			Token:     token,
			ExpiresAt: expiresAt,
			User:      user,
		})
	}
}

// Register handler
func Register(cfg *config.Config, log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req RegisterRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid request body",
				"details": err.Error(),
			})
			return
		}

		// TODO: Implement actual user registration logic
		// For production, implement:
		// 1. Email validation and uniqueness check
		// 2. Password strength validation
		// 3. Password hashing (bcrypt, argon2)
		// 4. Email verification workflow
		// 5. User profile creation
		// 6. Terms of service acceptance

		{{- if include_database }}
		// Database registration example:
		// // Validate email uniqueness
		// existingUser, _ := dbManager.GetUserByEmail(req.Email)
		// if existingUser != nil {
		//     c.JSON(http.StatusConflict, gin.H{"error": "Email already registered"})
		//     return
		// }
		//
		// // Hash password
		// hashedPassword, err := hashPassword(req.Password)
		// if err != nil {
		//     log.Errorf("Password hashing failed: %v", err)
		//     c.JSON(http.StatusInternalServerError, gin.H{"error": "Registration failed"})
		//     return
		// }
		//
		// // Create user
		// newUser := &User{
		//     Email:    req.Email,
		//     Name:     req.Name,
		//     PasswordHash: hashedPassword,
		//     CreatedAt:    time.Now(),
		//     IsVerified:   false,
		// }
		//
		// err = dbManager.CreateUser(newUser)
		// if err != nil {
		//     log.Errorf("User creation failed: %v", err)
		//     c.JSON(http.StatusInternalServerError, gin.H{"error": "Registration failed"})
		//     return
		// }
		{{- else }}
		// Mock registration - replace with real implementation
		{{- endif }}

		// For now, this is a mock implementation

		// Generate JWT token
		token, expiresAt, err := generateToken(cfg.JWTSecret, "2", req.Email)
		if err != nil {
			log.Errorf("Failed to generate token: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to generate token",
			})
			return
		}

		user := User{
			ID:    "2",
			Email: req.Email,
			Name:  req.Name,
		}

		c.JSON(http.StatusCreated, AuthResponse{
			Token:     token,
			ExpiresAt: expiresAt,
			User:      user,
		})
	}
}

// RefreshToken handler
func RefreshToken(cfg *config.Config, log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		// TODO: Implement token refresh logic
		// For production, implement:
		// 1. Validate current token
		// 2. Check token blacklist
		// 3. Verify user still exists and is active
		// 4. Generate new access token
		// 5. Optionally rotate refresh token
		// 6. Update token issued time

		var req struct {
			RefreshToken string `json:"refresh_token" binding:"required"`
		}

		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "Invalid request body",
				"details": err.Error(),
			})
			return
		}

		// Validate refresh token
		claims, err := parseToken(req.RefreshToken, cfg.JWTSecret)
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Invalid refresh token",
			})
			return
		}

		{{- if include_database }}
		// Verify user still exists in database
		// user, err := dbManager.GetUserByID(claims.UserID)
		// if err != nil || user == nil {
		//     c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found"})
		//     return
		// }
		// if !user.IsActive {
		//     c.JSON(http.StatusUnauthorized, gin.H{"error": "Account deactivated"})
		//     return
		// }
		{{- endif }}

		// Generate new access token
		newToken, expiresAt, err := generateToken(cfg.JWTSecret, claims.UserID, claims.Email)
		if err != nil {
			log.Errorf("Failed to generate new token: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to refresh token",
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"token": newToken,
			"expires_at": expiresAt,
		})
	}
}

// GetProfile handler
func GetProfile(log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetString("user_id")
		email := c.GetString("email")

		// TODO: Fetch user from database
		// For production, implement:
		// 1. Fetch complete user profile from database
		// 2. Handle user not found scenarios
		// 3. Return appropriate user fields
		// 4. Implement field selection/filtering
		// 5. Add caching for frequently accessed profiles

		{{- if include_database }}
		// Database implementation example:
		// user, err := dbManager.GetUserByID(userID)
		// if err != nil {
		//     log.Errorf("Failed to fetch user profile: %v", err)
		//     c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch profile"})
		//     return
		// }
		// if user == nil {
		//     c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		//     return
		// }
		//
		// // Return user profile (exclude sensitive fields)
		// profile := User{
		//     ID:        user.ID,
		//     Email:     user.Email,
		//     Name:      user.Name,
		//     CreatedAt: user.CreatedAt,
		//     UpdatedAt: user.UpdatedAt,
		//     // Don't include PasswordHash, sensitive data
		// }
		//
		// c.JSON(http.StatusOK, profile)
		{{- else }}
		// Mock profile - replace with real implementation
		user := User{
			ID:    userID,
			Email: email,
			Name:  "User Name",
		}

		c.JSON(http.StatusOK, user)
		{{- endif }}
	}
}

func generateToken(secret, userID, email string) (string, int64, error) {
	expiresAt := time.Now().Add(24 * time.Hour).Unix()

	claims := jwt.MapClaims{
		"user_id": userID,
		"email":   email,
		"exp":     expiresAt,
		"iat":     time.Now().Unix(),
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(secret))
	if err != nil {
		return "", 0, err
	}

	return tokenString, expiresAt, nil
}

// TokenClaims represents the claims in our JWT token
type TokenClaims struct {
	UserID string `json:"user_id"`
	Email  string `json:"email"`
	jwt.RegisteredClaims
}

func parseToken(tokenString, secret string) (*TokenClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &TokenClaims{}, func(token *jwt.Token) (interface{}, error) {
		return []byte(secret), nil
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*TokenClaims); ok && token.Valid {
		return claims, nil
	}

	return nil, jwt.ErrTokenInvalidClaims
}
