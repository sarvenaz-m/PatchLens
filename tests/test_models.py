import unittest
import numpy as np

from patchlens.models import Model, contrastive_loss, objective


class ModelTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(82)
        self.x=rng.normal(size=(4,3))
        self.y=np.array([0,1,0,1])

    def test_encoder_full_gradient_finite_difference(self):
        model=Model.create(3,'encoder',11,hidden=3,embedding=2)
        kwargs={'contrastive_weight':.3,'positive_weight':3.,'temperature':.4,'l2':.002}
        loss,grad,_=objective(model.params,self.x,self.y,**kwargs)
        epsilon=1e-6
        for key,param in model.params.items():
            for index in np.ndindex(param.shape):
                original=float(param[index]);param[index]=original+epsilon
                plus=objective(model.params,self.x,self.y,**kwargs)[0]
                param[index]=original-epsilon
                minus=objective(model.params,self.x,self.y,**kwargs)[0]
                param[index]=original
                with self.subTest(key=key,index=index):
                    self.assertAlmostEqual(float(grad[key][index]),(plus-minus)/(2*epsilon),delta=2e-5)

    def test_linear_gradient_finite_difference(self):
        model=Model.create(3,'linear',11)
        _,grad,_=objective(model.params,self.x,self.y,positive_weight=3.)
        for key,param in model.params.items():
            for index in np.ndindex(param.shape):
                original=float(param[index]);param[index]=original+1e-6
                plus=objective(model.params,self.x,self.y,positive_weight=3.)[0]
                param[index]=original-1e-6
                minus=objective(model.params,self.x,self.y,positive_weight=3.)[0]
                param[index]=original
                self.assertAlmostEqual(float(grad[key][index]),(plus-minus)/2e-6,places=7)

    def test_masked_contrastive_objective(self):
        # Matching views coincide; opposite classes point in opposite directions.
        z=np.array([[1.,0.],[-1.,0.],[1.,0.],[-1.,0.]])
        loss,_=contrastive_loss(z,self.y,.5)
        self.assertAlmostEqual(loss,float(np.log(1+2*np.exp(-4))),places=10)

    def test_contrastive_pair_order_required(self):
        with self.assertRaises(ValueError):contrastive_loss(self.x,np.array([0,1,1,0]))

    def test_training_reduces_objective_and_is_reproducible(self):
        a=Model.create(3,'encoder',5,hidden=4,embedding=3);b=Model.create(3,'encoder',5,hidden=4,embedding=3)
        h=a.fit(self.x,self.y,epochs=70,contrastive_weight=.2)
        b.fit(self.x,self.y,epochs=70,contrastive_weight=.2)
        self.assertLess(h[-1]['loss'],h[0]['loss'])
        np.testing.assert_array_equal(a.predict(self.x),b.predict(self.x))

    def test_checkpoint_preserves_predictions(self):
        model=Model.create(3,'encoder',9,hidden=4,embedding=2);model.fit(self.x,self.y,epochs=8)
        restored=Model.from_dict(model.to_dict(),3)
        np.testing.assert_array_equal(model.predict(self.x),restored.predict(self.x))

    def test_invalid_checkpoint_rejected(self):
        value=Model.create(3,'linear',4).to_dict();value['params']['head']=[1,2]
        with self.assertRaises(ValueError):Model.from_dict(value,3)


if __name__ == '__main__': unittest.main()
