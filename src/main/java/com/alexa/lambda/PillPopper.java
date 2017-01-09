package com.alexa.lambda;
import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;

public class PillPopper {
	public void handle(String blah, Context context) {
		LambdaLogger logger = context.getLogger();
	}
}
