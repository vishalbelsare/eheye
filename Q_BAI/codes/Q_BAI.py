from abc import ABC, abstractmethod
import numpy as np
from collections import defaultdict

# Version: May/2020
# This file implements Quantile-based Best Arm Identification Algorithms, including
# Fixed budget: Q-UGapEb; Q-SAR
# Fixed confidence: Q-UGapEc

# Benchmark algorithms: 
# Fixed budget: uniform sampling; batch elimination (functional bandit)
# Fixed confidence: uniform sampling; QPAC (Szorenyi et al. 2015); 
#                   Max-Q (David and Shimkin 2016); QLUCB (Howard and Ramdas 2019)


class Q_UGapE(ABC):
    """Base class. Quantile unified gap based exploration (BAI) algorithm.

    Attributes
    -------------------------------------------------------------------------
    env: list
        sequence of instances of Environment (reward distribution of arms).
    true_quantile_list: list
        sequence of tau-quantile of arms, i.e. {Q_i^\tau}_{i=1}^{K}
    epsilon: float (0,1)
        accuracy level
    tau: float (0,1)
        quantile level
    num_arms: int
        totoal number of arms K
    m: int
        number of arms for recommendation set 
    est_flag: boolean 
        indicate whether estimation the lower bound of hazard rate L
        True: estimate L
        False: use the true L = f(0)/ (1 - F(0)), where f is PDF and F is CDF
    fixed_L: list, default is None
        if not None, set L to fixed_L
    hyperpara: list of  [TODO]
        L_est_thr: L estimate threshold 
    
    m_max_quantile: float
        max^m Q_i^{tau} 
    m_argmax_arm: int
        arm index: argmax^m Q_i^{tau}
    sample_rewards: dict 
        keys: arm i in {0,1,2,.., K}; 
        values: list of sampled rewards for corresponding arm
    selectedActions: list
        sequence of pulled arm ID 
    true_L_list: list
        sequence of true L (lower bound of hazard rate)
        used to compare with the results with estimated L
    estimated_L_dict: dict
        keys: arm idx
        values: list of estimated L (len is the current number of samples)
    """
    def __init__(self, env, true_quantile_list, epsilon, tau, m, 
                hyperpara, est_flag, fixed_L):
        """
        Parameters
        ----------------------------------------------------------------------
        env: list
            sequence of instances of Environment (reward distribution of arms).
        true_quantile_list: list
            sequence of tau-quantile of arms, i.e. {Q_i^\tau}_{i=1}^{K}
        epsilon: float (0,1)
            accuracy level
        tau: float (0,1)
            quantile level
        m: int
            number of arms for recommendation set 

        hyperpara: list of  [TODO]
            L_est_thr: L estimate threshold 
        est_flag: boolean 
            indicate whether estimation the lower bound of hazard rate L
            True: estimate L
            False: use the true L = f(0)/ (1 - F(0)), where f is PDF and F is CDF
        fixed_L: list, default is None
            if not None, set L to fixed_L
        """

        self.env = env
        self.true_quantile_list = true_quantile_list
        self.epsilon = epsilon
        self.tau = tau
        self.m = m
        
        self.num_arms = len(self.env)
        self.m_max_quantile = np.sort(self.true_quantile_list)[::-1][self.m-1]
        self.m_argmax_arm = np.argsort(self.true_quantile_list)[::-1][self.m-1]

        self.sample_rewards = defaultdict(list)
        self.selectedActions = []

        self.hyperpara = hyperpara
        self.est_flag = est_flag
        self.fixed_L = fixed_L

        # For lower boudn of hazard rate
        self.true_L_list = []
        self.init_L()
        # for test of sensitivity
        self.estimated_L_dict = {}
    
    
    @abstractmethod
    def confidence_interval(self,t):
        """Compute the confidence interval D_i(t)

        Return 
        -----------------------------------
        D_list: list
            list of confidence intervals for arms of round t
        """

    @abstractmethod
    def simulate(self):
        """Simulate experiments. 
        """

    @abstractmethod
    def evaluate(self):
        """Evaluate the performance.
        """

    def init_reward(self):
        """pull each arm once and get the rewards as the initial reward 
        """
        for i, p in enumerate(self.env):
            self.sample_rewards[i].append(p.sample())

    def sample(self, idx):
        """sample for arm specified by idx

        Parameters
        -----------------------------
        idx: int
            the idx of arm with maximum ucb in the current round
        
        Return
        ------------------------------
        reward: float
            sampled reward from idx arm
        """
        reward = self.env[idx].sample()
        self.sample_rewards[idx].append(reward)
        return reward

    def select_arm(self, t, D_list):
        """SELECT ARM Algorithm.

        Parameters
        --------------------------------
        t: int
            the number of current round
        D_list: list
            list of confidence intervals for arms of round t

        Return:
        int: selected arm idx
        --------------------------------
        """
        ucb_list = []
        lcb_list = []
        B = []

        for arm in sorted(self.sample_rewards.keys()):
            reward = self.sample_rewards[arm]
            emp_quantile = np.quantile(reward, self.tau)
            D = D_list[arm]
            ucb[arm] = emp_quantile + D
            lcb[arm] = emp_quantile - D
        
        for arm in sorted(self.sample_rewards.keys()):
            B.append(np.max(ucb)[::-1][self.m] - lcb[arm])
            
        S_idx = np.argsort(B)[:m]
        non_S_idx = np.argsort(B)[m:]

        u_t = np.asarray[non_S_idx][np.argmax(np.asarray(ucb)[np.asarray[non_S_idx]])]
        l_t = np.asarray[S_idx][np.argmin(np.asarray(lcb)[np.asarray[S_idx]])]

        if D_list[u_t] >= D_list[l_t]:
            return u_t
        else:
            return l_t

    
    def init_L(self):
        """Initialise the true_L_list for the use of true L,
        where L is the lower bound of hazard rate.
        L = f(0)/ (1 - F(0))
        """
        for i in range(len(self.env)):
            
            my_env = self.env[i]
            
            if hasattr(my_env, 'hazard_rate'):
                # if existing attribute hazard rate
                L = my_env.hazard_rate(0)
            elif hasattr(my_env, 'pdf'):
                # if pdf and cdf is defined
                L = my_env.pdf(0)/ (1- my_env.cdf(0))  
            else:
                L = my_env.L_estimate(self.hyperpara[-1])
            #assert L > 0
            
            self.true_L_list.append(L)
        # print(self.true_L_list)
    
    def calcu_L(self, arm_idx):
        """estimate the lower bound L of hazard rate for 
           a reward distribution specified by arm_idx
           (with the assumption of non-decreasing hazard rate)
        
        Parameter
        ---------------------------------------
        arm_idx: int
            the index of arm needed to be estimate
        
        Return
        ----------------------------------------
        L: positive float
            the lower bound of hazard rate for arm idx
        """

        if self.est_flag:
            if self.fixed_L == None:
                # estimate L
                sorted_data = np.asarray(sorted(self.sample_rewards[arm_idx]))
                L = len(sorted_data[sorted_data <= self.hyperpara[-1]])/len(sorted_data)
                if L  == 0:
                    L = 0.1
            else:
                # use fixed L, for test of sensitivity
                L = self.fixed_L[arm_idx]

            if arm_idx in self.estimated_L_dict.keys():
                self.estimated_L_dict[arm_idx].append(L)
            else: 
                self.estimated_L_dict[arm_idx] = []
                self.estimated_L_dict[arm_idx].append(L)
            return L
        else:
            # true L = f(0)/ (1 - F(0))
            return self.true_L_list[arm_idx]
    

class Q_UGapEb(Q_UGapE):
    """Fixed budget.

    Arguments
    ---------------------------------------------------------------
    prob_error: float
        probability of error (evaluation metric)
    """
    def __init__(self, env, true_quantile_list, epsilon, tau, m, 
                hyperpara, est_flag, fixed_L, budget):
        """
        Parameters
        ----------------------------------------------------------
        budget: int
            number of total round/budget.
        """
        super().__init__(env, true_quantile_list, epsilon, tau, m, 
                hyperpara, est_flag, fixed_L)
        self.budget = budget

    def confidence_interval(self,t):
        """Compute the confidence interval D_i(t)

        Return 
        -----------------------------------
        D_list: list
            list of confidence intervals for arms of round t
        """

        for arm in sorted(self.sample_rewards.keys()):
            reward = self.sample_rewards[arm]
            emp_quantile = np.quantile(reward, self.tau)
            t_i = len(reward)
            k_i = int(t_i * (1- self.tau))
            L_i = self.calcu_L(arm)

            v_i = 2.0/(k_i * L_i ** 2)
            c_i = 2.0/(k_i * L_i)
            v_t = 4.0 /( t_i * L**2)

            [TODO]

    def simulate(self):
        """Simulate experiments. 
        """
        [TODO]

    def evaluate(self):
        """Evaluate the performance.
        """
        [TODO]
    

class Q_UGapEc(Q_UGapE):
    """Fixed confidence.
    """

    def __init__(self, env, true_quantile_list, epsilon, tau, m, 
                hyperpara, est_flag, fixed_L, delta):
        """
        Parameters
        ----------------------------------------------------------
        delta: float
            confidence level
        """
        super().__init__(env, true_quantile_list, epsilon, tau, m, 
                hyperpara, est_flag, fixed_L)
        self.delta = delta

    def confidence_interval(self,t):
        """Compute the confidence interval D_i(t)

        Return 
        -----------------------------------
        D_list: list
            list of confidence intervals for arms of round t
        """
        D_list = []

        for arm in sorted(self.sample_rewards.keys()):
            reward = self.sample_rewards[arm]
            emp_quantile = np.quantile(reward, self.tau)
            t_i = len(reward)
            k_i = int(t_i * (1- self.tau))
            L_i = self.calcu_L(arm)

            v_i = 2.0/(k_i * L_i ** 2)
            c_i = 2.0/(k_i * L_i)
            gamma = 0.5 * np.log(4 * self.num_arms * t **3/self.delta)

            D_i = np.sqrt(2 * v_i * gamma) + c_i * gamma
            D_list.append(D_i)

        return D_list

    def simulate(self):
        """Simulate experiments. 
        """
        self.init_reward()
        while 

    def evaluate(self):
        """Evaluate the performance.
        """
        [TODO]

class Q_SAR():